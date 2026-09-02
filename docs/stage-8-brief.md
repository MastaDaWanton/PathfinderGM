# Stage 8 — kickoff brief

Set up on 2026-09-02, not started. Everything an agent needs to begin is here or is
pointed at from here; nothing below has been run. The stage opens with the research
pass, as every stage does (CLAUDE.md, "How work is expected to be done").

## The stage as planned, and the measured extension

`docs/compliance-plan.md` names stage 8 as **feats as documents**: "16 of 1,474
computed, eight name-branches, a sixth modifier channel. Reuses the class `grants`
grammar — a feat is an ability you always have."

Two live probes on 2026-09-02 (stage 7's, recorded in `docs/stage-7-plan.md`) measured
the same law being broken from the other side. Asked to drink a potion the satchel did
not hold, the model emitted `heal` with `amount: "1d8+1"` and the engine applied it —
twice, in two separate probes. A number with no item, spell, ability or rule behind it
reached the sheet. `heal`, `damage`, `buff`, `temp_hp`, `defence`, `ability_damage` and
`item_damage` all take a model-written `amount` today; `buff`, `temp_hp` and `defence`
accept an optional free-text `source`, and the other four carry only `because`.

So the stage has two halves, and the recon's first job is to say which is the root and
whether they are one change or two:

1. **Feats as documents** — the plan's stage: a feat's mechanical content lives in a
   document the same `grants` grammar validates and applies, so a feat's bonus arrives
   the way a ring's does (through the applicator) and not through a name-branch in the
   engine.
2. **Effects come from documents** — the probe's stage: an effect op names a source the
   engine can resolve (a jar in the satchel, a prepared spell, a granted ability, a
   worn item, a shipped rule), and an unsourced number is refused at validate with the
   fix named. The model proposes *which document*; the document supplies the number.

Both are the third law. Neither adds per-class engine code (`docs/design-contract.md`,
"Zero per-class engine code").

## What exists to build on

- `content/classes/*.json` — the ability-document grammar (`paths.<path>.grants`),
  validated by `rules/classbuilder.py`, applied by `Engine._apply_ability_document`.
  `tests/test_ability_documents.py` pins it. This is the grammar stage 8 reuses.
- `content/feats/feats.json` — 1,474 imported feats (`rules/feats.py`: `Feat`,
  `all_feats`, `meets`, `available`, `search`). Prerequisites are evaluated
  (`rules/feats.py:_check`); mechanical content is not — the "16 computed" are
  name-branches somewhere in `rules/sheet.py` / `rules/engine.py`, and the map has to
  find every one.
- `rules/magicitem.py:worn_specs` — a worn item's effect specs, the worked example of a
  document supplying numbers through the applicator. `rules/effectspec.py` is the spec
  vocabulary (25,464 shipped specs; see the plan's "honest gap").
- `rules/consumables.py` — a jar's specs become intents on use; the one door today that
  turns a document into effect ops. `rules/casting.py` does the same for spells.
- `rules/dice.py:stack` and the typed `Modifier` — the aggregator; "a sixth modifier
  channel" is a claim about it that the map must verify.
- `Engine._check_legality` — where an unsourced number would be refused; stage 7 drew
  the line for what validate may reject (the model's errors, with the fix named).

## Research questions, per tradition

Primary sources only; say when a claim could not be sourced; a critic checks the
researchers. Look hardest for what each tradition **tried and abandoned**.

- **Unreal GAS**: `GameplayEffectContext` / `SourceObject`, how an effect carries its
  origin, and what `SetByCaller` magnitudes are for — the sanctioned way a runtime value
  enters an effect without the caller authoring the effect. Did Epic document why
  magnitudes live on the effect definition rather than the applying code?
- **Foundry VTT Active Effects**: the `origin` UUID on every effect, and how the system
  refuses/handles an effect whose origin no longer exists. What did the dnd5e system
  change between v9 and v11 about where item effects come from?
- **Pathfinder 1e itself**: how the rules define a feat's mechanics (benefit text with
  typed bonuses), which feats are pure prerequisites, and the typed-bonus stacking table
  — the ground truth the document grammar must express. Paizo's own PRD.
- **PCGen / Hero Lab / Pathbuilder data formats**: how feats are encoded as data (JEP
  formulas, "BONUS:" lines), what those formats could not express, and what their
  authors said about it. This is the closest prior art to "1,474 feats as documents".
- **Interactive fiction / MUD command validation**: how Inform's action rules and
  Evennia's command parsers refuse an effect the world cannot account for — the
  "where did this number come from" question in another register.

## Code-map subsystems

- `rules/feats.py` and every consumer of a feat by NAME across `rules/` (the sixteen).
- `rules/sheet.py` modifier computation: every channel a number can enter (the "sixth").
- `rules/engine.py` effect ops: `_op_damage`, `_op_heal`, `_op_buff`, `_op_temp_hp`,
  `_op_defence`, `_op_ability_damage`, `_op_item_damage`, `_op_condition` — what each
  reads, what it records as source, what validate checks.
- `rules/consumables.py`, `rules/casting.py`, `rules/magicitem.py`, `rules/leveling.py`
  — the four doors that already turn a document into effects.
- `gm/prompts.py` and `gm/judgement.py` — where the model is taught the effect ops,
  and every injector that emits one.
- The corpus: `content/feats/feats.json` shape, and what `rules/effectspec.py` could
  express of it.

## Acceptance, measured

- The probe `tools/probe_unsourced_effects.py` — "I drink my healing potion" with none,
  against the real model in a throwaway `CAMPAIGN_DIR` — produces no `heal` outcome
  with effects and no hit-point change. Today it produces `heal 1d8+1`.
- Zero name-branches on feats in `rules/engine.py` and `rules/sheet.py` (an AST ratchet
  in the `_CLOCK_SITES` shape, with the sixteen listed by reason as they are retired).
- A feat's bonus reaches a number on the sheet and names its source, through the same
  door a worn ring does — provable in `tools/prove_build.py` the way the ring already is.
- `tests/test_three_laws.py` gains: no effect op reaches the applicator without a
  resolvable source.
- The whole suite; the packaged exe; `prove_build` ALL CLEAN.

## Refused up front

- No model-authored numbers, anywhere, including "just this once" for GM fiat. The
  contract's answer to GM fiat is a *rule document* the GM cites.
- No per-class or per-feat engine code. A feat that "needs" a special case needs a
  field in the grammar.
- No second grammar. Feats reuse `grants`; if `grants` cannot express a feat, `grants`
  grows and the classbuilder validates the growth.

## Run order

1. `Workflow({name: "stage8-recon"})` — research, maps, critic. Read the result, then
   write `docs/stage-8-plan.md` in the shape of `docs/places-8b-plan.md`.
2. `Workflow({name: "stage8-design-review"})` — four refuters over the plan, then a
   synthesis. Amend the plan.
3. Implement in the worktree, per substage, with the probe after each.
4. `Workflow({name: "stage8-verify"})` — adversarial verification against a live
   campaign, then the ratchet audit.
5. Suite, exe, `prove_build`, commit per substage in the repo's narrative style, merge.
