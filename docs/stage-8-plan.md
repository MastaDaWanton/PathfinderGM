# Stage 8 — every number points at a document

Written 2026-09-02 from the recon (`stage8-recon`: three of five research reports and
all six code maps landed; the Foundry and PCGen reports are still owed and are folded
in under "Amendments" when they arrive). Kickoff brief: `docs/stage-8-brief.md`. Parent:
`docs/compliance-plan.md`, stage 8. Shape follows `docs/places-8b-plan.md`.

The brief asked the recon one question first: are "feats as documents" and "effects
come from documents" one change or two? **One principle, two surfaces.** The principle
is the third law read literally: *no model authors a number* — so every number that
lands on a sheet must be traceable to a document the engine resolved. The feat half
breaks it from inside the code (fourteen feats' numbers are Python literals a
name-branch adds outside the funnel); the probe half breaks it from the model's side
(the sampler is offered `heal` with a free `amount`, and the prompt's own worked
example is `heal 1d8+1`). They share one field and one rule, and are built as
separate substages because they touch different files.

## What the sweep settled

Primary sources, as the researchers cited them; two overclaims in the brief are
corrected here rather than carried.

- **The definition declares the slot; the caller may only fill it.** GAS splits an
  effect into a *definition* (an asset: "Gameplay effects should NOT contain blueprint
  graphs"), a *spec* (the runtime binding: "What UGameplayEffect — What Level — Who
  instigated") and a *context* (`Instigator`, `EffectCauser`, `SourceObject`: "Object
  this effect was created from"). A runtime value enters through `SetByCaller`: the
  definition names a slot (`DataName`/`DataTag`), the applying code supplies a value for
  that slot and nothing else — it "cannot rename the attribute, change the operation,
  or add a modifier". Epic abandoned name-keyed slots for tag-keyed ones ("the tag
  version should normally be used"). This is the shape: **the document owns the
  arithmetic; the runtime owns a choice and an origin.**
- **A number with no table row does nothing.** CircleMUD's `call_magic` — "the very
  heart of the entire magic system … all come through this function eventually" —
  takes an identity (`spellnum`) and one scalar (`level`) and computes the amount
  *inside* the routine from `spell_info[spellnum]`; an out-of-range spell number
  returns 0. Diku Gamma's per-spell C functions were abandoned for that data row, and
  its compiled-in `dam_each[level]` arrays with an `assert` on the level for a dice
  expression plus a `level/4` term. Refusals are ordinary output before any world
  change ("Cast what where?", "You are unfamiliar with that spell.").
- **In 1e a feat's number is never the player's.** Every Core benefit is a literal in
  the text or a formula over a sheet statistic; the player's runtime input is a
  *choice* — activate or not, which weapon the feat is bound to. The rules refuse by
  arithmetic, not by rejecting a proposal: same type takes the best; dodge,
  circumstance and untyped stack; the same feat twice yields nothing more. Paizo fenced
  dodge bonuses to feats and class features ("Spells and magic items should never
  grant dodge bonuses because dodge bonuses always stack") and retrofitted a same-source
  rule by FAQ when untyped-stacks-with-anything proved exploitable. Dodge's bonus is
  lost whenever the Dex bonus to AC is lost; Power Attack "does not apply to touch
  attacks or effects that do not deal hit point damage."
- **What the sources refuse to sanction**: logic inside the effect asset (GAS, refused
  from the start); a caller that authors the effect rather than filling a declared slot
  (GAS); a spell whose mechanics live in code rather than a row (Diku → Circle); an
  enumerated table of what an ability bonus touches (Paizo FAQ 2013, abandoned for
  "anything relating to that ability"). Nothing read refuses a number for lacking a
  *named* source — 1e defaults an untyped bonus to "stacks with anything". That
  refusal is this project's own rule, and the plan says so.

## What the maps corrected in the brief

- **"16 computed" is fourteen, plus three families the count missed.** Toughness
  (`hp_bonus`) and Point-Blank Shot (`ranged_near`) sit in `rules/tables.py:FEATS` and
  are read by nothing; the sheet page prints "bonus hit points" for a feat that adds
  none. Outside the table, three more branches apply feats by name: `improved`/`greater
  <maneuver>` by f-string (`rules/sheet.py:1586`), `* weapon proficiency` by suffix
  (`:1382`), and Combat Reflexes by substring in `rules/reactions.py:96`. Weapon Focus
  +1 and Weapon Specialization +2 are literals in the sheet; the table's copies are
  dead. Dodge is declared `dodge` in the table and emitted untyped. `validate()` writes
  "carried as flavour; engine applies nothing" onto 1,458 feats, including three
  families the engine does apply.
- **The sixth channel is real.** Every feat term is a bare `Modifier` appended inside a
  builder (`skill_modifiers`, `save_modifiers`, `initiative_modifiers`,
  `attack_modifiers`, `damage_modifiers`, `ac_modifiers`, `cmb_modifiers`) — never
  through `_buff_mods`, never typed, never removable by removing an effect. The sheet
  map counted fifteen distinct ways a number reaches the sheet; the worn-gear path
  (`_standing_mods`, live-read from slots so `take_off` removes it) is the one the
  brief already calls law-compliant, and it is the one feats will copy.
- **`rules/casting.py` is not a spell door.** Its own docstring says it computes DC,
  slots and caster level and does not derive what a spell does. The spell door is
  `spells.casting_plan` → `Engine._op_cast` / `_run_specs` / `Scene._resolve_on`.
- **The model was taught the number.** `gm/prompts.py:296-300` — the twelfth worked
  example — is `heal {"amount": "1d8+1"}` for "drink the flask"; the briefing at 583
  says "A potion, a poultice, a spell that mends: heal". The probe's output is the
  prompt's example returned verbatim. `use_item` is taught nowhere. In a fight the
  sampler enum (`_FIGHT_OPS`) admits `damage` and `heal` for the player *and* the NPC
  turn, and `npc_turn` runs no injectors and no review.
- **The engine's own potion is indistinguishable from the model's.**
  `consumables._spec_to_intents` emits `heal` with a string amount and only `because`;
  the jar's id is dropped before validate. A source gate at validate cannot tell the
  jar's heal from the model's unless the door stamps provenance the model cannot write.
- **The list of model-authored numbers is longer than seven.** Besides `heal`,
  `damage`, `buff`, `temp_hp`, `defence`, `ability_damage`, `item_damage`: `save`'s
  `on_failure.damage`/`on_success.damage` dice, `compel.penalty` (an unbounded model
  integer), `guard.amount`/`range_ft`/`uses`, and `resource` gain (any pool name,
  created on demand, dice amount). None is value-checked anywhere.
- **`grants` cannot host a feat as it stands.** Its only locator is
  `actor.paths → path.grants` (`rules/leveling.py:121`); `_apply_ability_document`
  needs a toggle key; standing modifiers are refused unless the ability is a toggle or
  `passive`; the only scaling axis is `control_blood`; and two formula vocabularies
  disagree (`resources.variables` raises on an unknown name, `effectspec.FORMULA_VARS`
  returns 0). Of 1,474 benefits, 76% carry a conditional word and 15% are parameterised
  by a chosen thing; hand-classified, 8 of the 79 single-sentence "+N bonus" feats are
  expressible by today's grammar. A full conversion is not this stage.
- **Three number stores sit outside the effect store** and can record no source:
  `Actor.ability_damage`/`ability_drain` dicts, `Gear.hp`, `Pool.current`, plus
  `scene.guards`. "Every effect reaches the applicator with a source" is provable at
  the *intent*, not on those sheets; the plan claims the former.

## The four decisions the maps forced

**1. Provenance is a field the model cannot write.** Every effect-bearing intent
carries `params["origin"]`, a document reference of the form `kind:id` —
`item:<stock id>`, `spell:<spell id>`, `ability:<path>/<key>`, `feat:<feat id>`,
`worn:<slot>`, `rule:<rule id>`, `author:cheat`. `origin` joins
`intents.ENGINE_OWNED_PARAMS`, so a model-written one is refused at parse with the
fix named, exactly as a model-written `dc` is today. Every engine door stamps it:
`consumables._spec_to_intents` (the jar's id), the spell plan (the spell id),
`_op_use_ability`'s effects loop (the ability), wards (the spell), the cheat clerk
(`author:cheat`). `ActiveEffect` gains `origin` beside `source`: `source` stays the
display label the popup and the tell show; `origin` is what a test can resolve. GAS's
context has both (`SourceObject` and the display of who instigated); Foundry names the
field `origin`. The word is theirs on purpose.

**2. The model proposes the document; the sampler is not offered the number.** On
player and NPC turns the seven amount-ops leave `turn_schema`'s enum, and the four
outliers lose their number params (decision 4). What the model may say is `use_item
item=<id>`, `cast spell=<id>`, `use_ability name=<x>`, `condition` (the number is in
`tables.CONDITIONS`), and — new — `hazard rule=<id>` for the GM-fiat cases the brief
refused to leave unsourced: falling, fire, acid, cold, drowning, from a shipped
`content/rules/hazards.json` transcribed from the Core Rulebook's Environment chapter.
The worked example and the briefing lines are rewritten to name documents;
`use_item` gets the declarer it never had, so "I drink my healing potion" opens the
jar door when the satchel holds one and prints stage 7's refusal when it does not.
Validate keeps a backstop — an amount-op without `origin` is refused with "Name what
heals: use_item item=<id> for a jar, cast spell=<id>, use_ability name=<x>" — but the
backstop is for the engine's own bugs; the model never sees the op. This is the
sampler-schema lesson from `docs/stage-7-plan.md`: a validate-time rejection taught
the model to route around; an enum it cannot emit from has no route. The cheat path
is untouched: `/cheat` is the author's hand, `CHEAT_OPS` keeps the amount-ops, and
`keep_the_authors_numbers` stamps `author:cheat`. "No model-authored numbers" is not
"no author-typed numbers", and the plan refuses to conflate them.

**3. Feats are live-read standing effects, like worn gear — not stored `ActiveEffect`s.**
The migration lens decides this before it is asked. A stored effect applied at load
must answer "once, twice or never" for every save that predates it, must survive
snapshot/restore and level-up, and must be removed when the feat is. A live read has
no such questions: `Actor.feats` *is* the store, `_feat_mods` is computed from the
feat documents inside `_buff_mods` beside `_standing_mods`, and removing the string
removes the term — the exact property the worn-ring check in `tools/prove_build.py`
already proves. This is GAS's infinite-duration passive with the asset as the source
of truth, and it is what the sheet map already calls law-2 compliant for gear. Feat
mechanics live in `content/feats/mechanics.json`, keyed by feat **id** (two Foeslayers
and 155 mythic name-clashes rule out names), one entry per feat in the same `grants`
vocabulary the classbuilder validates — `modifiers[{kind,target,amount,bonus_type}]`,
`tags`, `formula` — reached by a second *locator* (`feats.document(feat_id)`), never a
second *grammar*. The OGL text in `feats.json` is not edited.

**4. `grants` grows by six fields, each named by a feat that needs it, and the
classbuilder validates every one.** The brief's "if `grants` cannot express a feat,
`grants` grows" is now a list:

| Field | Feat that forces it | Meaning |
|---|---|---|
| `scope.weapon: "$target"` on a modifier | Weapon Focus, Weapon Specialization | the sheet's parenthetical `(rapier)` binds the term to that weapon key; an untargeted feat binds nowhere (today it binds everywhere) |
| `attack_ability: "dex"` + `when.weapon.finessable` | Weapon Finesse | ability substitution; not a modifier, a switch the attack builder reads from the document |
| `formula` over `bab`, `hit_dice`, `dex_mod`; `when.weapon.hands` | Power Attack, Toughness, Combat Reflexes | one formula vocabulary — `resources.evaluate`, which raises on an unknown name; `effectspec.FORMULA_VARS` is folded into it rather than kept as a second |
| `toggle` on a feat document | Power Attack | the per-attack *choice* stays the model's boolean `power_attack`; the *numbers* (`-(1 + bab // 4)` attack, twice that damage, ×1.5 two-handed) come from the document, and `can_power_attack`'s hard-coded prerequisites go |
| `tags: ["proficient.martial"]` | the Weapon Proficiency family, Improved Unarmed Strike | permissions are tags; `is_proficient` asks `has_state("proficient.martial")` (law 1) instead of matching a suffix |
| `budget.attack_of_opportunity: "1 + dex_mod"` | Combat Reflexes | a count, not a modifier; `reactions.budget_for` reads the document |
| `when.range_ft <= 30` | Point-Blank Shot | a per-roll condition; the attack op passes range into the builder context. Shipped in this stage only if the context plumbing is small; otherwise the document carries the condition and a listed test pins that it is not yet honoured |

Two generic rules ride along, neither per-feat: dodge-typed modifiers are dropped
while `lose_dex_to_ac` (1e's rule, currently unimplemented for all 24 dodge feats),
and a feat's `improved <maneuver>` family is one document template expanded over
`MANEUVERS`, applied to CMB *and* CMD (today CMB only — a 1e gap the branch
reproduced).

## The shape

```json
{
  "weapon-focus": {
    "modifiers": [{"kind": "combat_mod", "target": "attack", "amount": 1,
                   "bonus_type": "untyped", "scope": {"weapon": "$target"}}]
  },
  "dodge": {
    "modifiers": [{"kind": "combat_mod", "target": "ac", "amount": 1, "bonus_type": "dodge"}]
  },
  "toughness": {
    "modifiers": [{"kind": "combat_mod", "target": "hp_max",
                   "formula": "3 + max(0, hit_dice - 3)", "bonus_type": "untyped"}]
  },
  "power-attack": {
    "toggle": "power_attack",
    "modifiers": [
      {"kind": "combat_mod", "target": "attack", "formula": "-(1 + bab // 4)"},
      {"kind": "combat_mod", "target": "damage", "formula": "2 * (1 + bab // 4)"},
      {"kind": "combat_mod", "target": "damage", "formula": "1 + bab // 4",
       "when": {"weapon": {"hands": 2}}}
    ]
  },
  "combat-reflexes": {"budget": {"attack_of_opportunity": "1 + dex_mod"}},
  "martial-weapon-proficiency": {"tags": ["proficient.martial"]}
}
```

An intent with provenance, as the jar door emits it and the model never can:

```json
{"op": "heal", "actor": "pc", "because": "the draught",
 "params": {"amount": "1d8+1", "origin": "item:potion-of-cure-light-wounds#3"}}
```

## Persistence

Nothing new is saved. Feat effects are recomputed from `Actor.feats` on every read;
`SAVE_VERSION` does not move. `ActiveEffect.origin` round-trips through
`to_dict`/`from_dict` with `""` for effects saved before this stage (an old save's
buff keeps its label and simply has no resolvable origin — the law test is about what
*arrives*, not what was already there). `validate()`'s "carried as flavour" note is
rewritten to be true: it is appended only when the feat has neither a mechanics
document nor a code consumer, and the stale copies in existing saves are stripped on
load by the same guard that stops it re-appending.

## The validator

`classbuilder.validate_feat_document(feat_id, doc)` reuses `_validate_grants`'s
modifier, tag and formula checks and adds the six fields. Every message names the
fix: "`scope.weapon` must be `$target` or a weapon key; this feat is written
`weapon focus (rapier)` on the sheet, so `$target` binds to `rapier`"; "no formula
variable `str_mod`; the vocabulary is: bab, hit_dice, level, dex_mod, …". A document
for a feat id not in `feats.json` is refused. `python -m rules.classbuilder` (the
existing CLI) gains the feats file, and the suite validates the shipped file on
import the way it validates spells and creatures — the map found `magic-items.json` is
the one corpus with no load-time validator, and this stage does not add a second.

## 8a — provenance, and the sampler stops offering numbers

Files: `rules/intents.py` (`origin` engine-owned; amount-ops keep `amount` for the
doors, gain required `origin`), `rules/activeeffect.py` (`origin`), `rules/engine.py`
(`_check_legality` backstop; every `_op_*` copies `origin` onto the effect record and
the tell names the origin's display name — today heal/damage/ability_damage/
item_damage tells name no source, so the narrator could not have said what healed),
`rules/consumables.py` / `rules/spells.py` / `_op_use_ability` / wards (stamp),
`gm/prompts.py` (`turn_schema` enum without the amount-ops for player and NPC turns;
the heal example and the briefing lines rewritten to `use_item`/`cast`; `use_item` in
`_op_reference` and the examples), `gm/judgement.py` (a `use_item` declarer before the
survival `_DRINKS` sip; `refuse_unknown_ability`'s jar branch injects `use_item` instead
of returning the model's heal untouched), `gm/agent.py` (`plan_cheat` stamps
`author:cheat`). Probe: `tools/probe_unsourced_effects.py` three of three clean, and
its inverse — the same sentence with a real jar lands a heal whose outcome carries
`origin: item:…`.

## 8b — feat documents through the worn-gear door

Files: `content/feats/mechanics.json` (the fourteen, Toughness, Point-Blank Shot's
document, Dodge typed), `rules/feats.py` (`document(feat_id)`, the id lookup from a
sheet string — one normaliser, replacing the four the map counted), `rules/classbuilder.py`
(the validator), `rules/sheet.py` (`_feat_mods` inside `_buff_mods`; the four table
loops at 1217/1257/1276/1521 deleted; `hp_max` reads its channel for Toughness),
`rules/tables.py` (`FEATS` reduced to display names, then deleted when nothing reads
it). Tests that pin source strings (`'Stealthy' in breakdown sources`) keep passing
because the label is the feat's name. Probe: `/api/sheet` shows the feat named among
the terms the way the ring is; remove the feat, the number moves back; a save
round-trip applies it once.

## 8c — the branches, and the grammar that retires them

Files: `rules/sheet.py` (Weapon Focus/Specialization literals → scoped documents;
`_uses_finesse` → `attack_ability`; `power_attack_terms` and `can_power_attack` →
the toggle document; `improved <maneuver>` → the template family on CMB and CMD;
`is_proficient` → tags), `rules/reactions.py` (Combat Reflexes → `budget`),
`rules/tables.py` (`power_attack_terms` deleted), `rules/leveling.py` /
`rules/resources.py` (one formula vocabulary; `effectspec` evaluates through it).
`tests/test_engine.py:325-331` pins BAB 8 two-handed Power Attack at +9 today and must
still. The AST ratchet `_FEAT_SITES` in `tests/test_three_laws.py` lists every retired
branch with its reason and fails on a new `has_feat(`/`FEATS.get(` in a builder.
Probe: Weapon Focus + masterwork + a +1 morale buff on one attack roll, terms read
from the engine's actual roll: focus and masterwork stack (untyped with enhancement),
morale takes the best of morale.

## 8d — the outliers

`save`'s branch dice come only from a document (a spell's plan or a hazard rule);
the standalone `save` op keeps `on_failure.condition`. `compel.penalty` is the table's
number, not a param. `guard`'s numbers come from the granting ability's document. The
model's `resource` gain branch goes; pools refresh by document. `content/rules/
hazards.json` ships with the CRB Environment numbers and the `hazard` op cites it.
Probe: "I jump from the wall" against the model produces `hazard rule=falling` and
damage whose origin is `rule:falling`, never a bare `damage`.

## 8e — the ratchet

`tests/test_three_laws.py` gains: (1) every amount-op intent that reaches an `_op_*`
carries a resolvable `origin` (walked by driving each door in a test scene);
(2) `origin` is engine-owned and a model-written one is refused with the fix named;
(3) the prompt teaches no number — `EXAMPLES` and `BRIEFING` contain no `"amount"`
on an amount-op, and `turn_schema`'s player/NPC enum contains none of the seven;
(4) `_FEAT_SITES`: zero `has_feat`/`FEATS` reads in builders, the retired sixteen
listed by reason; (5) `content/feats/mechanics.json` validates on import.
`tools/prove_build.py` gains the feat check beside the ring check. The skill ledger,
`docs/compliance-plan.md` and the memory note move stage 8 to shipped.

## Refused

- **A stored `ActiveEffect` per feat**, applied on load or level-up. Every question the
  migration lens would ask (once/twice/never, restore, level-up, removal) is answered by
  not storing it. Rage is a toggle with a lifetime; a feat is not.
- **Feat-by-name anywhere in `rules/`**, including "just the suffix match for
  proficiency". Tags, or a document field.
- **A second grammar or a second formula evaluator.** Six new fields in `grants`, one
  vocabulary; `effectspec`'s evaluator is retired into `resources.evaluate`.
- **Converting the corpus.** 1,474 feats, 76% conditional; the stage ships documents for
  every feat the code names today and the grammar for the next hundred, not the
  conversion. `validate()` says which feats have no document, truthfully.
- **Refusing the author's numbers.** `/cheat` keeps the amount-ops with
  `origin: author:cheat`. The law is about the model.
- **A validate-time source check as the primary defence.** It stays as the engine's
  backstop; the sampler enum is the defence. Stage 7 measured what a validate-time
  rejection teaches a model.
- **`origin` as a free string.** `kind:id`, resolved by the engine (`rules/provenance.py`
  resolves each kind against the satchel, the spellbook, the class documents, the feat
  file, the slots, the rules file), or refused.
- **GM fiat with no rule.** The hazards file is the answer; a hazard not in it is a
  narrated fall that hurts nobody until someone writes the row — and the refusal says
  which file.

## What the two late reports settled

The Foundry and PCGen reports arrived after the first draft and bear on decision 3
directly, so they are recorded here rather than rewritten into the top.

- **Foundry tried the stored-effect-with-a-pointer design and abandoned it.** From 0.8
  to v10 an item's effects were *copied* onto the actor with `origin` set to the item's
  UUID, and core deleted actor effects whose origin matched a deleted item. v11
  introduced `legacyTransferral = false`: "ActiveEffects will never be copied to
  Actors" — the effect stays inside the item and `Actor#allApplicableEffects()`
  enumerates it, so provenance is *structural* (the effect's parent is the item).
  The v11 article gives the reason: origin "historically had problems where unlinked
  Tokens or Actors housed in compendia were concerned", and the lead's verdict on the
  dangling-origin bug was "the heart of this issue is a wontfix". dnd5e 3.0.0 adopted
  it; V14 removed core's last assignment of `origin`. That is decision 3 in another
  engine: **the feat list is the store; the number is read off the document while the
  feat is held.** `ActiveEffect.origin` here is what Foundry freed the field for — who
  applied an effect from outside — not a dependency the applicator checks.
- **The PF1e Foundry system is the direct prior art for the grammar.** A feat is an
  item whose mechanics are `Change` records: `{formula, operator: add|set, target,
  type, priority}`, `target` from a closed `buffTargets` list (each with the bonus
  types it accepts), `type` from a closed `bonusTypes` list with
  `stackingBonusTypes = {untyped, untypedPerm, dodge, racial, circumstance}`; dodge
  bonuses to AC are skipped under `loseDexToAC`. Formulas are evaluated over roll
  data (`@attributes.hd.total`, `@cl`); dice in a change formula are *maximised*,
  never rolled, unless the target is flagged `deferred` and rolled at roll time.
  Toughness ships as `formula: max(3, @attributes.hd.total)`, `target: mhp`. Arbitrary
  JavaScript in the formula slot ("script changes") was deprecated in 9.0 and removed
  in 10.0; three parallel provenance stores (Changes, SourceInfo, source details) were
  called "largely unnecessary tripling" and merged. Write-time validation of change
  targets is commented out because it "does not work reliably for much anything but
  skills" — the validator here is load-time and refuses, which is the other choice.
- **PCGen's LST is the same shape twenty years earlier.** `BONUS:COMBAT|AC|1|TYPE=Dodge`,
  `BONUS:SAVE|Will|2`, `DEFINE:PowerAttackModifier|0` + `BONUS:VAR|…|(BAB/4)+1`,
  `CHOOSE:SKILL|…` with `%LIST` substituted into the bonus (the `$target` binder),
  `TEMPBONUS` for activated feats, `AUTO:WEAPONPROF` for proficiencies. An undeclared
  variable "has no effect and … effectively remain[s] at zero" — PCGen drops silently
  where this plan refuses at validate. PCGen abandoned its formula engine (JEP) for
  "race conditions, and recycling" and the pre-JEP syntax before that. Hero Lab
  refuses by validation report. Nothing in any of the four formats has a channel
  through which an unsourced number could arrive — the model-side half of this stage
  has no prior art because no prior system let a language model propose numbers.

## Amendments from the adversarial review

Four refuters, then a synthesis that re-checked every disputed line against the code.
What follows is the synthesis as delivered, with the section headings demoted; each
amendment supersedes the sentence it names above. The implementation sequence at the
end replaces the substage sections 8a–8e where they differ.

Every disputed claim below was checked against the worktree code before the verdict. Line references are to the files as they stand today.

### A. Amendments (breaks-the-design / breaks-a-feature)

**A1. Provenance cannot travel in `params`. (lens 2 — RIGHT)**
Verified: `rules/intents.py:597-599` pops engine-owned params silently (the comment at 378-387 records why hard rejection was removed); `dc` is an *optional* param on `check`/`save` (:196-197), not engine-owned; every door goes through the same `parse_all`. The plan's decision 1 misdescribes the mechanism and, taken literally, strips the jar door's own stamp.
Replace decision 1's second and third sentences with:
> `origin` lives on the `Intent` object as an engine-only attribute (`Intent.origin`, default `""`), never in `params`. It is set after parse by the one trusted path, `Engine.validate(raw, origin=...)`, which stamps every `Intent` it returns; the jar door calls `self.validate(use.intents, origin=f"item:{item_id}")`, `plan_cheat` passes `origin="author:cheat"`, tests pass `origin="author:test"`. A model-written `params["origin"]` is refused in `parse_all` by an explicit check ahead of the engine-owned pop — "`origin` is the engine's; say use_item item=<id> / cast spell=<id>" — because the engine-owned set *ignores*, it does not refuse, and the plan must not claim otherwise.

**A2. Resolve the referent at stamp time, not at validate. (lens 2 — RIGHT)**
Verified: `rules/engine.py:3572-3576` decrements and pops the stock entry *before* the effects are validated ("spent before the effects resolve"); the last dose of any stack is gone from `actor.stock` when its own heal is checked. `_op_cast` spends the slot before resolution too (:3838-3852).
Add to "Refused — `origin` as a free string":
> Resolution happens in the door while it still holds the document: the jar door resolves `held` at :3555 and stamps `item:<stock id>` plus the display name; the cast door stamps `spell:<id>` from the plan it already has. `provenance.resolve()` checks that an origin is well-formed and of a known kind; the 8e ratchet asserts it was stamped by a door, not that the referent still exists — a potion's last dose has no stock row by the time its heal lands, and that is the ordinary case, not an edge.

**A3. Bestiary creatures have no document to cite once `damage` leaves the NPC enum. (lens 2 — RIGHT)**
Verified: `rules/bestiary.py:296-303` strips `special_attacks`, `special_abilities`, `spell_like` and `feats`; `leveling.find_ability` (:248-262) walks `actor.paths` only, which a spawned monster lacks. After 8a a spider's poison bite has no legal op.
Add to decision 2:
> A bestiary actor's turn is the exception this stage names rather than hides: 5,735 of 7,188 shipped creatures carry `special_attacks` and 2,163 carry `spell_like`, and no locator reads either. On a non-path actor's NPC turn the enum keeps `damage` and `ability_damage`; `npc_turn` stamps `origin: creature:<slug>` (the engine names the source, the model still authors the number), the ratchet excludes that one door by name with the count, and the creature-document stage that retires it is added to `docs/compliance-plan.md`. The alternative — dropping the ops and letting every monster go toothless silently — is stage 7's lesson in reverse and is refused.

**A4. Toughness: `hp_max` is not a target and the setter would double-count. (lens 1, lens 3, lens 4 — RIGHT, three lenses)**
Verified: `rules/effectspec.py:60-64` `combat_target` has no `hp_max`; `rules/sheet.py:852-875` derives `hp_max` and `set_hp_max` stores the inverse; `from_dict` calls `set_hp_max(data["hp_max"])`, so a live feat term inflates `hp_base` by +3 on every save/load — the Thor 23→37 class of bug.
Add to 8b:
> `hp_max` joins `combat_target` (validator and vocabulary). The channel is symmetric the way Constitution is: `hp_max` adds `_feat_mods("combat_mod", "hp_max")` and `set_hp_max(total)` subtracts the same sum before storing `hp_base`. The 8b probe round-trips the sheet **twice** (`to_dict → from_dict → to_dict → from_dict`) and asserts `hp_max` unchanged; the test docstring records the measurement "+3 per reload without the inverse".

**A5. `has_state` reads stored-effect tags only; a live-read feat's tags are invisible. (lens 1, lens 3 — RIGHT)**
Verified: `rules/sheet.py:1152` is `any(states.matches(t, q) for e in self.effects for t in e.tags)`; class proficiencies are plain tuples in `tables.CLASSES`. Implemented as written, a feat-only martial proficiency eats -4 on every swing.
Replace the `tags` row of the six-field table with:
> `has_state` gains a documented second source, `standing_tags()`: the `tags` of every held feat's document plus the class proficiency list rendered as `proficient.<category>` / `proficient.weapon.<key>`. It is the one door for stored *and* standing tags (docstring at :1145 amended to say so). The feat's tag is `proficient.weapon.<$target>` — Martial Weapon Proficiency is one weapon per taking; today's whole-category grant from `split()[0]` (:1383) is a bug the document must not enshrine — and `proficient.martial` is a class tag only. Pin: Kesst's rapier proficient, a fighter holding only the feat proficient with that weapon, a wizard with a longsword -4.

**A6. `toggle` collides with an existing grammar word and round-long choices need a lifetime. (lens 1 — RIGHT)**
Verified: `rules/classbuilder.py:286-301` `toggles` already means a standing state applied via `_apply_ability_document`; `rules/intents.py:202` lists `power_attack` as an attack param.
Replace the `toggle` row with:
> `choice: "power_attack"` — the name of a boolean the `attack` op may carry for this feat id; the validator refuses a choice name not in the attack op's optional params. A choice whose benefit outlives the swing (Combat Expertise, Deadly Aim, Lunge — "until your next turn") is a 1-round `ActiveEffect` applied through `_apply_ability_document`, stated as the one exception to decision 3: it is a lifetime, so it is stored. Power Attack's three modifiers carry `when.weapon.category: melee`; light and off-hand weapons get a half rung.

**A7. The modifier funnel has no context; `scope`/`when`/`choice` have nothing to evaluate against. (lens 1, lens 3 — RIGHT)**
Verified: `_buff_mods(self, kind, target)` at :2226 and `_standing_mods` at :542 take two arguments at all twelve call sites; the weapon key and `power_attack` bool are local to `attack_modifiers`/`damage_modifiers`. Measured by lens 3: Power Attack through the funnel lands on the plain longsword (+5→+4) and on a shortbow.
Add to decision 3:
> The funnel becomes `_buff_mods(kind, target, ctx: dict | None = None)`; `ctx` carries `weapon` (key, hands, category, finessable, light/off-hand), `power_attack`, `range_ft`, `maneuver`, and is threaded from `attack_modifiers`, `damage_modifiers`, `cmb_modifiers` and `cmd_modifiers` (which gains a `maneuver` argument the engine's maneuver resolution passes). Every other caller passes none. A `scope`/`when`/`choice` term whose key is absent from `ctx` is **dropped**, never applied — Point-Blank Shot "not yet honoured" means dropped. One plumbing job serves Weapon Focus, Power Attack, Point-Blank Shot and `improved <maneuver>`. Pin: Borin `attack_modifiers("dagger")` shows no Power Attack term; `("longsword", power_attack=False)` totals +5; `("shortbow", power_attack=True)` carries no Power Attack term and an empty damage list.

**A8. `resources.variables` is eager and recurses through `hp_max`/`ability_mod`. (lens 3 — RIGHT)**
Verified: `rules/resources.py:52-77` reads `actor.hp_max` and every `ability_mod` before any formula is walked.
Add to the formula row:
> `variables()` becomes a lazy mapping (a name is computed on first access), and `_feat_mods` carries a re-entrancy guard that answers `[]` while already on the stack, so `hp_max → _feat_mods → evaluate → variables` never touches `hp_max` for a formula over `hit_dice`, and a formula that does name the channel it feeds contributes 0 with a validator warning rather than a `RecursionError`. Pin: Toughness on a level-1 sheet gives +3 and `ability_mod("con")` returns.

**A9. The forge only writes untargeted Weapon Focus. (lens 3, lens 4 — RIGHT)**
Verified: `rules/creation.py:467` writes `feats_mod.get(fid).name.lower()`; no level-up feat writer exists. Under the plan every forge-built holder goes from +1 everywhere to +1 nowhere, and `tools/prove_build.py:344`, `tests/test_creation.py:25,161`, `tests/test_houserules.py:31` all seed the bare form.
Add to 8c:
> The forge gains a weapon picker for any feat whose document carries `$target`, accepting `{"id": "weapon-focus", "target": "longsword"}` and writing `weapon focus (longsword)`; a build naming such a feat without a target is refused with the fix named. On load, a bare `$target` feat on a PC is bound once to `equipped` and the string rewritten with a note on the sheet — never silently dropped. `prove_build.py:344`, `test_creation.py:161` and `test_houserules.py:31` are updated; "tests that pin source strings keep passing" is true only of skill and save feats. Pin: Durga longsword +5 before and after, dagger +4 after.

**A10. The 8c probe's masterwork term has no channel. (lens 3 — RIGHT)**
Verified: `blacksmith._quality_specs` writes an enhancement spec onto the crafted record; `_standing_mods` reads `SLOTS` + `worn` only, no weapon slot; `_op_wear` sets `equipped` and nothing else.
Rewrite the 8c probe:
> Weapon Focus + a +1 *enhancement*-typed buff + a +1 morale buff on one live attack roll: focus and enhancement stack, morale takes the best of morale. The wielded-weapon spec channel (masterwork, enchanted) has zero readers today and is listed in the sheet map as the sixteenth way a number should reach the sheet and does not; it is stage 9, not this one.

### B. Lines to add

- **Grammar field name.** The document grammar writes `type` (what `classbuilder.py:907-912` and `sheet.py:559` read); `kind` is the applied-record field (`engine.py:5168`). Correct every modifier in "The shape" and say `_feat_mods` translates the way `_apply_ability_document` does.
- **Feat actions after 8a.** Cleave, Vital Strike, Spring Attack, Arcane Strike are `use_ability`-shaped; their documents carry `effects` (the list `validate_effect` already accepts) resolved by a `feats.document` branch in `find_ability`. Until that ships, `refuse_unknown_ability` names the feat and says "this feat has no document yet", and the sampler keeps `attack` for the swing.
- **One evaluator with a context.** `resources.evaluate(formula, actor, extra: dict | None = None)` merges the cast context (`caster_level`, `spell_level`) over sheet variables; `check()` accepts the union; the merged vocabulary is listed in the plan and gains `ranks` (bound to the modifier's own skill target). Test: a spell with `amount: "spell_level + caster_level"` still resolves after the fold.
- **`$target` is a general binder** — weapon, skill, school, maneuver — not `scope.weapon` alone; Skill Focus (+3, +6 at 10 ranks) is the first document that needs it.
- **The validator refuses what the appliers do not honour.** Unknown keys on feat modifiers are refused (`effectspec.validate` never rejects unknown keys today); the six new fields are refused in class-path documents until `_apply_ability_document` honours them, so a Rage modifier with `when:` cannot pass validation and land unconditional.
- **Partial documents say so.** A document carries `not_yet: ["reaction.aoo.flat_footed"]` for a clause the engine has no reader for (Combat Reflexes' flat-footed half, Improved Trip's no-provoke), each with a pinning test; `validate()`'s note distinguishes "no document", "document, partly honoured" and "honoured". Combat Reflexes' budget is `"1 + max(0, dex_mod)"`, matching `reactions.py:96-97`. `tests/test_rules.py:196` moves its example to a feat with neither document nor consumer.
- **Feats on flat-stat actors.** `_feat_mods` contributes nothing to a channel whose `flat_*` is set — the printed total already includes the feat (every feat loop today sits under the `else` of the flat branch, :1257/:1270/:1498; `_buff_mods` runs after it). `bestiary.py:302` stripping `feats` stays deliberate. Pin: `flat_saves.will = 0` + "iron will" answers +0.
- **Weapon Finesse keeps its third clause.** `_uses_finesse` (:1334-1339) applies only when `dex_mod > str_mod`; the grammar is `attack_ability: {"use": "dex", "if_better": true}`. Pin a Str 16 / Dex 12 holder.
- **Which doors carry provenance where.** On the intent: jar, cheat, hazard, test. On the effect record and the tell: cast, use_ability, ward, the save branch, attack, rest. 8e(1) is a walk over `Outcome.effects` where every `heal`/`damage`/`temp_hp`/`buff` record names a top-level `origin`; the walker reads only those record kinds, because `spells.area()` already writes `origin: "you"/"point"` on area records (`spells.py:639-641`).
- **Hazard rows declare slots.** `falling: {"slot": "distance_ft", "min": 10, "max": 200, "dice": "1d6 per 10 ft"}`; the `hazard` op takes exactly the declared slot names, validates the range from the row, and the 8d probe asserts the effect record carries the slot value. This is the plan's own SetByCaller reading applied to the one op it invents. Traps are named in Refused as narrated-only this stage.
- **All five teaching sites.** `gm/prompts.py:298, 584, 586, 590, 613`. Ability damage from disease is narration-only this stage and :590 is dropped deliberately; poison from a jar is `use_item`, from a creature the A3 exception.
- **The 23 bare-amount test sites** use `engine.validate(raw, origin="author:test")` and are listed as 8a work, so the suite is not patched by writing origins into raw dicts.
- **`_NAMED_IN_ENGINE["rules/sheet.py"]`** (`tests/test_three_laws.py:895-925`, lower bound `hits >= ceiling - 1`) is lowered to 1 in the same commit as the 8c deletions.
- **`use_item` in `CHEAT_OPS`.** `use_item` is `player`-visible (:274) and therefore absent from `CHEAT_OPS`; state that the cheat clerk keeps the amount-ops and does not need it.

### C. Missing items that are load-bearing

1. The trust boundary for provenance outside `params` (A1) — without it every other provenance line is unimplementable.
2. A context-bearing funnel signature and the list of callers that pass it (A7).
3. A locator for creature specials, or the named exception with its count (A3).
4. The inverse of the Toughness channel in `set_hp_max` and the save-twice assertion (A4).
5. The recursion guard on `variables` (A8).
6. `standing_tags()` as `has_state`'s second source, including class proficiencies (A5).
7. The forge writer and load-time binding for `$target` feats; a statement that no level-up feat writer exists and what string form it must one day produce (name + parenthetical target, resolved through the one normaliser) (A9).
8. The unevaluable-condition rule: dropped (A7).
9. Hazard slots with bounds (B).
10. A locator for feat *actions* in `find_ability` (B).

### D. Implementation sequence

**8a — provenance and the sampler.** Files: `rules/intents.py` (`Intent.origin`; explicit refusal of a model-written `origin`), `rules/engine.py` (`validate(raw, origin=)`; jar door stamps while `held` is in hand; cast/use_ability/ward/save/rest copy `origin` onto effect records and tells), `rules/consumables.py`, `rules/activeeffect.py`, `rules/provenance.py`, `gm/prompts.py` (player enum minus the seven; the five teaching sites; `use_item` in `_op_reference`), `gm/judgement.py` (`use_item` declarer; jar branch injects `use_item`), `gm/agent.py` (`author:cheat`; bestiary-NPC exception stamped `creature:<slug>`), the 23 test sites. **Probe:** a PC carrying exactly one `potion-of-cure-light-wounds#1` says "I drink my healing potion" in a live scene — the outcome carries a heal with `origin: item:potion-of-cure-light-wounds#1`, the satchel is empty afterwards, and `tools/probe_unsourced_effects.py` reads three of three clean.

**8b — grammar, funnel and documents.** Files: `rules/effectspec.py` (`hp_max` target; unknown-key refusal), `rules/resources.py` (lazy `variables`; `evaluate(..., extra)`; `ranks`), `rules/leveling.py`/`rules/engine.py` (effectspec evaluates through resources), `rules/classbuilder.py` (`validate_feat_document`; six fields refused in class docs), `rules/feats.py` (`document()`, normaliser), `content/feats/mechanics.json` (the flat set, Toughness, Dodge typed, Point-Blank Shot with `not_yet`), `rules/sheet.py` (`_buff_mods(kind, target, ctx)`; `_feat_mods` with re-entrancy guard and flat-stat guard; symmetric `hp_max`/`set_hp_max`; `standing_tags()` in `has_state`; four table loops deleted), `rules/tables.py`, `tests/test_rules.py:196`. **Probe:** `/api/sheet` for Kesst shows `Stealthy` among Stealth's terms the way the ring shows; add `toughness` to a live Con+2 level-1 fighter, save and reload twice, `hp_max` reads 16 both times; remove the feat, it reads 13.

**8c — the branches.** Files: `rules/sheet.py` (Weapon Focus/Specialization → `$target` scope; `_uses_finesse` → `attack_ability` with `if_better`; Power Attack → `choice` + melee `when`; `is_proficient` → `has_state("proficient.weapon.<key>")`; `cmd_modifiers(maneuver=)`; `improved <maneuver>` template), `rules/reactions.py` (`budget`), `rules/creation.py` (weapon picker; refusal), load-time binding of bare `$target` feats, `rules/tables.py` (`power_attack_terms` gone), `tests/test_three_laws.py` (`_NAMED_IN_ENGINE` → 1; `_FEAT_SITES`), `tools/prove_build.py:344`, `tests/test_creation.py:161`, `tests/test_houserules.py:31`, `tests/test_engine.py:325-331` still +9. **Probe:** Borin in a live scene under a +1 enhancement buff and a +1 morale buff attacks with the longsword with `power_attack=true`: the roll's terms read BAB, Str, Weapon Focus, enhancement, morale, Power Attack −1 and damage +2; the same turn with the shortbow shows no Power Attack term.

**8d — the outliers and hazards.** Files: `content/rules/hazards.json` (rows with declared slots and bounds), `rules/intents.py` (`hazard` row; `compel.penalty`/`guard` numbers/`resource` gain removed), `rules/engine.py` (`_op_hazard`; `save` branch dice from a document only), `gm/prompts.py` (`hazard` taught; traps refused as narrated). **Probe:** "I jump from the thirty-foot wall" against the live model yields `hazard rule=falling distance_ft=30`, a 3d6 damage record whose `origin` is `rule:falling` and whose record carries `distance_ft: 30`, and "I set off the trap" yields narration and no damage record.

**8e — the ratchet.** Files: `tests/test_three_laws.py` (the five tests, with the bestiary exception excluded by name and count), `tools/prove_build.py` (feat check beside the ring check), `docs/compliance-plan.md`, the skill ledger, the memory note. **Probe:** `tools/prove_build.py` against the packaged build and a throwaway data directory seeded with a pre-stage save holding `weapon focus`, `iron will` and `toughness`: every term on the sheet names its document, the bare Weapon Focus is bound to `equipped` with its note, and `hp_max` matches the pre-stage save's printed total.

## Status

**8a shipped, 2026-09-03.** `Intent.origin`/`origin_name` stamped by
`Engine.validate(raw, origin=...)` after parse; a model-written `origin` refused at
parse with the doors named; `AMOUNT_OPS` refused at legality without a stamp; the
sampler enum carries none of the seven on player or NPC turns, with the bestiary
creature's fight turn as the one named exception (`_CREATURE_OPS`, `creature:<template>`);
the jar door, the coating door, the cheat clerk and the tests stamp; heal, damage,
ability-damage and item-damage tells name the document; `ActiveEffect.origin` on
buffs, temporary pools, defences and stance documents; the brief lists the satchel by
id; `declare_use_item` runs before survival and the jar branch of
`refuse_unknown_ability` opens the door instead of standing aside. Measured against
the live model (`tools/probe_unsourced_effects.py`): empty satchel, three of three —
`use_item item="healing potion"` and the printed refusal, hit points unmoved; with a
Healing Draught, three of three — `use_item item=healing-draught#1`, a heal record
with `origin: item:healing-draught#1`, the tell "from Healing Draught", the jar spent.
The inverse probe first failed three of three on a synonym ("healing potion" against
"Healing Draught", an exact-id lookup), which is why `consumables.resolve_stock`
exists: Inform's word-match-then-ask, shared by the door, the legality check and the
declarer. Fifty-four test sites stamp `author:test`. Not yet: `_op_use_ability`'s
instant effects loop records no per-number origin (the outcome record carries
`ability:<path>/<key>`); wards stamp `ward:<name>`, not a spell id; 8d's outliers.

**8b shipped, 2026-09-03.** `content/feats/mechanics/core.json` (a subfolder, because
`all_feats` globs `content/feats/*.json` as feat lists) carries twelve documents in the
`grants` modifier vocabulary — the five skill feats, the three save feats, Improved
Initiative, Dodge typed `dodge` at last, Toughness as `3 + max(0, hit_dice - 3)` on the
new `hp_max` target, Point-Blank Shot with its `when` and a `not_yet`. `feats.document`
is the one normaliser (name, id, or "Weapon Focus (rapier)"); `documents()` validates
on first load through `classbuilder.validate_feat_documents`, which refuses unknown
keys and unknown fields with the fix named. `Actor._feat_mods` reads them inside
`_buff_mods` beside worn gear; a `scope`/`when` term is dropped, never applied; a
formula is guarded against re-entry, and `resources.variables` is lazy — eager, it
read `hp_max` before walking any formula and recursed on every hit-point read.
`hp_max` reads the channel and `set_hp_max` subtracts it. The four table loops are
gone (`test_the_four_table_loops_are_gone_from_the_sheet`), the dodge/lose-Dex rule is
one generic line in `_buff_mods`, the page's feat text is generated from the document,
and `validate()`'s "carried as flavour" is only written for a feat with neither
document nor table entry. Measured: Toughness +3 with the sheet saved and reloaded
three times through the API in a throwaway data directory, `hp_max` 12 / base 8 each
time and 9 without the feat; `Stealthy` named among the Stealth terms on
`/api/sheet`; the whole suite 2,902 passed; the live feat read costs 0.25 ms per four
channel reads with four feats held. Still in the table until 8c: Weapon Finesse,
Weapon Focus, Weapon Specialization, Power Attack.

**8c shipped, 2026-09-03.** Forty documents now (twelve from 8b, Weapon Focus and
Specialization with `scope.weapon: "$target"`, Weapon Finesse as `attack_ability` with
`if_better` and `when.weapon.finessable`, Power Attack as `choice: "power_attack"` with
five conditional formula rungs — melee only, light +1, one-handed +2, two-handed +3 per
step — Combat Reflexes as `budget`, the three Weapon Proficiency feats as
`proficient.weapon.$target` tags, and the twenty Improved/Greater manoeuvre feats
generated over `MANEUVERS`, each scoped to its manoeuvre on CMB *and* CMD). The funnel
carries a context: `_buff_mods(kind, target, ctx)` with the weapon (key, hands,
category, light, finessable), the `power_attack` choice and the manoeuvre, threaded
from the attack, damage, CMB and CMD builders; `_scope_holds`/`_when_holds` evaluate,
and a key the context lacks drops the term. `has_state` reads `standing_tags()` — feat
tags and the class proficiency list — beside stored effects, so `is_proficient` is a
tag question. `can_power_attack` reads the prerequisites from feats.json (`meets`);
the hard-coded BAB 1 / Str 13 copy is gone, and so are `tables.FEATS`,
`tables.power_attack_terms`, `Actor.has_feat`, `_uses_finesse`, the suffix match and
the substring match. The forge takes `{"id": "weapon-focus", "target": "longsword"}`
and refuses a scoped feat with no target naming the fix; `from_dict` binds a bare
one to the weapon in hand with a note, once. `_NAMED_IN_ENGINE["rules/sheet.py"]` is
1 (Blood Bending, stage 9). Measured live in a throwaway campaign: Borin under a +1
enhancement oil and two +1 morale songs, Power Attack on — longsword terms BAB +1,
Str +3, oil +1 (enhancement), one song +1 (morale; the second did not stack),
Power Attack −1, Weapon Focus +1; damage Str +3, Power Attack +2; the shortbow
carried neither feat. 2,909 passed.
