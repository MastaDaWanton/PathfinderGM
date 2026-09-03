export const meta = {
  name: 'stage8-recon',
  description: 'Stage 8 reconnaissance: primary-source research on effect provenance, code maps of every number channel, and a critic over both',
  whenToUse: 'Launch once, before docs/stage-8-plan.md is written. Reads docs/stage-8-brief.md for scope.',
  phases: [
    { title: 'Research', detail: 'five traditions, primary sources, what they abandoned' },
    { title: 'Map', detail: 'every channel a number enters the sheet by, and every feat name-branch' },
    { title: 'Critic', detail: 'refute overclaims; find sites the maps missed' },
  ],
}

const REPO = 'H:/coding/PathfinderGM/.claude/worktrees/gracious-ishizaka-a20934'
const CONTEXT = `Repository: ${REPO} (a git worktree; read and grep only there). Read ${REPO}/docs/stage-8-brief.md FIRST and in full: it is the kickoff brief and carries the scope, the measured defect, what exists to build on, and what is refused. Then read CLAUDE.md and docs/design-contract.md for the laws. Be economical with the repository: grep, then read what the grep found.`

// Phase gating, added after a usage limit killed all twelve agents at once: run with
// args {only: ['research']}, then {only: ['maps']}, then {only: ['critic'], prior: {research, maps}}.
const ONLY = (args && args.only) || ['research', 'maps', 'critic']
const PRIOR = (args && args.prior) || {}

const RESEARCH_SCHEMA = {
  type: 'object',
  properties: {
    tradition: { type: 'string' },
    how_an_effect_carries_its_source: { type: 'string', description: 'the field/mechanism, exactly, with the document that defines it' },
    how_a_runtime_number_enters: { type: 'string', description: 'the sanctioned way a value computed at apply time gets into an effect without the applying code authoring the effect (e.g. SetByCaller)' },
    how_feats_or_passives_are_encoded: { type: 'string', description: 'as data: the grammar, what it can and cannot express' },
    what_is_refused: { type: 'string', description: 'what the system refuses or drops when provenance is missing or the source is gone' },
    abandoned: { type: 'array', items: { type: 'string' }, description: 'designs tried and dropped, with the reason and the source' },
    sources: { type: 'array', items: { type: 'string' } },
    unsourced: { type: 'array', items: { type: 'string' }, description: 'claims above you could not confirm in a source you actually read' },
  },
  required: ['tradition', 'how_an_effect_carries_its_source', 'how_a_runtime_number_enters', 'how_feats_or_passives_are_encoded', 'what_is_refused', 'abandoned', 'sources', 'unsourced'],
}

const MAP_SCHEMA = {
  type: 'object',
  properties: {
    subsystem: { type: 'string' },
    sites: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          file_line: { type: 'string' },
          kind: { type: 'string', enum: ['number-from-model', 'number-from-document', 'feat-name-branch', 'modifier-channel', 'source-recorded', 'source-dropped', 'other'] },
          expression: { type: 'string' },
          note: { type: 'string', description: 'what it reads, what it records as the source, what would break if the number had to come from a document' },
        },
        required: ['file_line', 'kind', 'expression', 'note'],
      },
    },
    channels: { type: 'array', items: { type: 'string' }, description: 'every distinct path a number takes onto the sheet (the aggregator, buffs, temp pools, flat_* fields, overrides, feat branches, ...) with file:line' },
    risks: { type: 'array', items: { type: 'string' } },
  },
  required: ['subsystem', 'sites', 'channels', 'risks'],
}

phase('Research')
const TRADITIONS = [
  { key: 'gas', prompt: 'Unreal Engine Gameplay Ability System. Primary sources: the official GAS documentation and the GameplayAbilities plugin source (GameplayEffect.h/.cpp, GameplayEffectTypes.h, FGameplayEffectContext, FGameplayEffectSpec, SetByCaller magnitudes, UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf). How does an applied effect carry its SourceObject/Instigator/EffectCauser? What is SetByCaller for, and what is the documented reason magnitudes live on the effect definition rather than in the applying code? What does the ASC do with an effect whose source is gone? Anything Epic documented as changed or deprecated in this area.' },
  { key: 'foundry', prompt: 'Foundry VTT Active Effects and the dnd5e/pf1 systems. Primary sources: the Foundry API docs for ActiveEffect (origin, transfer, changes[] with mode/key/value/priority), the Foundry community wiki on Active Effects, and the dnd5e system changelog/source for how item-granted effects are applied and what happens when the origin item is deleted. What is the origin UUID for, what does the core do when it cannot resolve it, and what did the dnd5e or pf1 system change about effect provenance across major versions? Also: how the pf1 system (foundryvtt-pathfinder1) encodes feat mechanics as data (its "changes" formulas) and what it could not express.' },
  { key: 'pf1', prompt: 'Pathfinder 1e rules as written. Primary sources: Paizo PRD / Archives of Nethys Core Rulebook chapters on Feats (benefit, prerequisites, special), Combat (bonus types and stacking), and the Glossary bonus-type table. How is a feat\'s mechanical benefit expressed in the rules text — typed bonuses, unlocked actions, changed numbers — and roughly what fraction of Core feats are pure prerequisites/unlocks versus numeric? What are ALL the bonus types and the stacking rule for each? This is the ground truth a feat-document grammar must express; report shapes, not opinions.' },
  { key: 'datafmt', prompt: 'How feats are encoded as data in PCGen, Hero Lab, and Pathbuilder (and the pf1e FoundryVTT system if not covered elsewhere). Primary sources: PCGen\'s LST file documentation (BONUS: tokens, PRExxx prerequisites, JEP formulas), Hero Lab\'s authoring kit docs (eval scripts), and anything Pathbuilder\'s author has written about the data model. What can each grammar express, what needed a script escape hatch, and what did their authors say they would do differently? Look for the boundary where data stops and code starts, because that boundary is stage 8\'s design decision.' },
  { key: 'if-validation', prompt: 'How interactive fiction and MUD engines refuse a change the world cannot account for. Primary sources: Inform 7\'s Writing with Inform on the action processing rulebooks (before/instead/check/carry out/report), Evennia docs on commands and the object model, and DikuMUD/CircleMUD spell/skill tables (spells.c, spell_parser.c: how a spell\'s numbers come from the table and not the caller). The question in another register: where does a number that changes the world have to come from, and what happens when code asks for one with no table behind it?' },
]
const PICK_T = (args && args.traditions) || null
const research = !ONLY.includes('research') ? Promise.resolve(PRIOR.research || []) : pipeline(TRADITIONS.filter(t => !PICK_T || PICK_T.includes(t.key)), t => agent(
  `You are researching prior art for stage 8 of a rules-engine compliance programme. ${CONTEXT}\n\nSearch the internet and read PRIMARY sources; a blog post counts only when its author is the tradition's own. ${t.prompt}\n\nReport ONLY what you confirmed in a source you actually read. Anything you believe but could not confirm goes in 'unsourced'. Cite the exact document for each claim. Say plainly when a question has no answer in the sources.`,
  { label: `research:${t.key}`, phase: 'Research', schema: RESEARCH_SCHEMA }))

phase('Map')
const SUBSYSTEMS = [
  { key: 'feats', focus: 'rules/feats.py in full, and EVERY consumer of a feat by name across rules/ gm/ play/ (grep for feats, has_feat, "Power Attack", "Weapon Focus", "Toughness", "Combat Reflexes", "Improved Initiative", "Dodge", "Skill Focus", feat names in strings). The plan says sixteen feats are computed through eight name-branches: find every one, with file:line, what number it changes and through which channel. Also content/feats/feats.json: its shape, its counts key, and three representative entries (a pure prerequisite feat, a typed-bonus feat, an unlock feat).' },
  { key: 'sheet-channels', focus: 'rules/sheet.py: every path a number takes onto the sheet. The aggregator (rules/dice.py:stack, Modifier), add_buff, gain_temp_hp, active effects (apply_effect/tick_effects), flat_* fields, overrides, kit/gear, natural_armour, and any arithmetic that adds to a stat outside the modifier funnel. The plan calls feats "a sixth modifier channel" — enumerate the channels and say which is the sixth. Report each with file:line and whether removing its source would remove its contribution (law 2).' },
  { key: 'engine-effect-ops', focus: 'rules/engine.py: _op_damage, _op_heal, _op_buff, _op_temp_hp, _op_defence, _op_ability_damage, _op_item_damage, _op_condition, _op_resource (gain), _op_compel, _op_guard. For each: where the number comes from (intent.params["amount"], a dice string rolled hidden), what it records as source (params.source, because, nothing), and what validate (_check_legality, rules/intents.py _check_params) checks about it. Also _apply_ability_document and _ability_refusal, the one path where a DOCUMENT supplies the numbers — describe its contract precisely, because stage 8 reuses it.' },
  { key: 'document-doors', focus: 'rules/consumables.py (plan/_spec_to_intents), rules/casting.py, rules/magicitem.py (worn_specs), rules/leveling.py (find_ability, resolve_effect), rules/effectspec.py (the spec vocabulary, and which types are engine=False). These are the four doors that already turn a document into effect ops or modifiers. For each: input document shape, what it emits (intents? modifiers? ActiveEffects?), and how the emitted thing carries its provenance. Where do the four disagree, and which one should the others converge on?' },
  { key: 'gm-side', focus: 'gm/prompts.py and gm/judgement.py: where the model is TAUGHT the effect ops (examples, briefing lines, the op reference in cheat_messages, turn_schema), and every injector or repair that EMITS heal/damage/buff/temp_hp/defence/condition/ability_damage/item_damage. Also gm/agent.py narrate paths that read those outcomes. If an effect op were to require a source document, what in the prompts and injectors would have to change, and what would the model be shown to choose from?' },
  { key: 'corpus', focus: 'The shipped content as data: content/feats/feats.json (all of it: shape, counts, the distribution of what the benefit text contains — typed bonuses, unlocks, prerequisites-only), content/classes/*.json grants grammar (every field the classbuilder validates: read rules/classbuilder.py validators), and content/spells + content/materials effect specs as consumed by rules/effectspec.py. The question: could the grants grammar express the feats as they are written, and for what fraction? Sample twenty feats across kinds and say for each whether grants expresses it, and if not what field would be needed. Numbers, not impressions.' },
]
const PICK_S = (args && args.subsystems) || null
const maps = !ONLY.includes('maps') ? Promise.resolve(PRIOR.maps || []) : pipeline(SUBSYSTEMS.filter(s => !PICK_S || PICK_S.includes(s.key)), s => agent(
  `${CONTEXT}\n\nYou are mapping ONE subsystem for stage 8: ${s.key}. Focus: ${s.focus}\n\nUse grep and read the actual code. Report file:line for everything. Do not propose designs; map. Be exhaustive within your subsystem — a missed site is a bug in the refactor.`,
  { label: `map:${s.key}`, phase: 'Map', schema: MAP_SCHEMA }))

const [found, mapped] = await Promise.all([research, maps])
const research_ok = found.filter(Boolean)
const maps_ok = mapped.filter(Boolean)
log(`research: ${research_ok.length}/${TRADITIONS.length}; maps: ${maps_ok.length}/${SUBSYSTEMS.length}`)

phase('Critic')
const critic = !ONLY.includes('critic') ? null : await agent(
  `${CONTEXT}\n\nYou are the critic. Below are (A) research reports on how traditions bind an effect to its source and encode passives as data, and (B) code maps of every channel a number takes onto the sheet in this repository. REFUTE, do not summarise.\n\nFor (A): find overclaims — a claim not supported by the cited source, or contradicted by it. Open the cited sources yourself to spot-check. Then state in one paragraph what the traditions GENUINELY agree on about (1) where an effect's provenance lives, (2) how a runtime value enters without the caller authoring the effect, (3) where the data/code boundary for passives fell in practice and why.\n\nFor (B): grep the code. Are there number channels or feat name-branches NO map covers? List them with file:line. Are the "sixteen computed feats" and "eight name-branches" and "sixth modifier channel" claims from the plan borne out, and what are the actual numbers? Which of the four document doors do the maps disagree about?\n\nEnd with the five highest-risk facts for the stage, each one sentence, and a recommendation on whether the two halves in the brief (feats as documents; effects come from documents) are one change or two, with the reason.\n\n(A) RESEARCH:\n${JSON.stringify(research_ok, null, 1)}\n\n(B) MAPS:\n${JSON.stringify(maps_ok, null, 1)}`,
  { label: 'critic', phase: 'Critic' })

return { research: research_ok, maps: maps_ok, critic }
