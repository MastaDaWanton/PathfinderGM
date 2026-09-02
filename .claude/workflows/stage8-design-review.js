export const meta = {
  name: 'stage8-design-review',
  description: 'Adversarially refute docs/stage-8-plan.md through four lenses, then synthesise the amendments',
  whenToUse: 'Launch after docs/stage-8-plan.md is written and before any code. Reads the plan, the brief, and the recon output if present.',
  phases: [
    { title: 'Refute', detail: 'four lenses, each trying to break the plan' },
    { title: 'Synthesise', detail: 'what must change before code is written' },
  ],
}

const REPO = 'H:/coding/PathfinderGM/.claude/worktrees/gracious-ishizaka-a20934'
const CONTEXT = `Repository: ${REPO} (a git worktree; read and grep only there). The plan under review is ${REPO}/docs/stage-8-plan.md — read it in full first; if it does not exist, stop and return a single refutation saying so. Its kickoff brief is docs/stage-8-brief.md and its parent is docs/compliance-plan.md. The laws are in CLAUDE.md and docs/design-contract.md; the grammar the plan reuses is validated by rules/classbuilder.py and applied by Engine._apply_ability_document (rules/engine.py). Read the actual code for anything you assert. Be economical: grep, then read what the grep found.`

const VERDICT = {
  type: 'object',
  properties: {
    lens: { type: 'string' },
    refutations: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          why_wrong: { type: 'string', description: 'concrete: a file:line, a scenario, a measurement' },
          severity: { type: 'string', enum: ['breaks-the-design', 'breaks-a-feature', 'needs-a-line-in-the-plan', 'nitpick'] },
          fix: { type: 'string' },
        },
        required: ['claim', 'why_wrong', 'severity', 'fix'],
      },
    },
    survives: { type: 'array', items: { type: 'string' } },
    missing: { type: 'array', items: { type: 'string' } },
  },
  required: ['lens', 'refutations', 'survives', 'missing'],
}

phase('Refute')
const LENSES = [
  { key: 'grammar', prompt: 'LENS: the grammar. The plan reuses `grants` for feats. Take twenty feats from content/feats/feats.json across kinds (typed bonus, unlock, prerequisite-only, conditional bonus like Dodge, per-round choice like Power Attack, resource like Combat Reflexes) and try to write each as a grants document that rules/classbuilder.py would ACCEPT and Engine._apply_ability_document would APPLY. For each that cannot be written, name the missing field. Attack "a feat is an ability you always have": which feats are not always-on, and what does the plan do with them?' },
  { key: 'provenance', prompt: 'LENS: provenance. The plan makes effect ops name a source the engine resolves. Attack it with every emitter of heal/damage/buff/temp_hp/defence/condition in gm/judgement.py and gm/prompts.py, every worked example, and the NPC-turn path: what source would each name, and what happens to the shipped worked examples that show a bare number? Attack the resolution rule with a source that exists at validate and is gone at resolution (a jar used earlier in the list, a spell slot spent). Attack GM fiat: falling damage, environmental damage, a trap — what document do those cite, and is there one?' },
  { key: 'stacking', prompt: 'LENS: the aggregator and the sixth channel. Read rules/dice.py:stack and every Modifier producer in rules/sheet.py. If feats become documents applied through the applicator, which typed channels do their bonuses land in, do they stack correctly with the existing sources (Weapon Focus + a masterwork weapon + a buff), and what does the plan do about feats that today live in a name-branch the aggregator never sees (a to-hit added outside the funnel)? Find a feat whose retirement from a branch CHANGES a number on a shipped fixture character, and say by how much.' },
  { key: 'migration', prompt: 'LENS: the shipped characters and saves. Feats are on actor sheets as name strings (rules/sheet.py feats: list[str]; fixtures/pc-*.json; the roster). If a feat becomes a document applied as an ActiveEffect, what happens on load to a character whose feat was a name-branch yesterday: is the effect applied once, twice, or never; does it survive a save; does snapshot/restore cover it; what does the level-up flow (rules/leveling.py, play/views.py level-up) do when a feat is chosen? Attack the plan\'s migration sentence, or its absence.' },
]
const verdicts = await Promise.all(LENSES.map(l => agent(
  `${CONTEXT}\n\nYou are one of four adversarial reviewers. Your job is to REFUTE the plan through one lens, with concrete evidence from the code. Default to finding the flaw; a decision only 'survives' if you attacked it specifically and it held. ${l.prompt}\n\nFor every refutation give file:line and the scenario. Rate severity honestly — 'breaks-the-design' means the plan cannot be implemented as written.`,
  { label: `refute:${l.key}`, phase: 'Refute', schema: VERDICT })))
const ok = verdicts.filter(Boolean)
log(`refuters: ${ok.length}/4; refutations: ${ok.reduce((n, v) => n + v.refutations.length, 0)}`)

phase('Synthesise')
const synthesis = await agent(
  `${CONTEXT}\n\nFour reviewers attacked the plan through four lenses. Their verdicts are below. Produce the amendment list: for each refutation rated breaks-the-design or breaks-a-feature, decide whether it is RIGHT (check the code yourself where the two disagree) and write the exact change to the plan — a sentence the plan should now contain, in the plan's own register. Group needs-a-line-in-the-plan items under 'lines to add'. Drop nitpicks unless two reviewers raised the same one. Then list the 'missing' items you agree are load-bearing. End with an ordered implementation sequence naming, for each substage, the files touched and the ONE probe that proves it against a live scene.\n\nVERDICTS:\n${JSON.stringify(ok, null, 1)}`,
  { label: 'synthesis', phase: 'Synthesise' })

return { verdicts: ok, synthesis }
