export const meta = {
  name: 'stage8-verify',
  description: 'Adversarial verification of stage 8 after implementation: probes against a live campaign, a ratchet audit, and a completeness critic',
  whenToUse: 'Launch after the stage 8 code is in the worktree and the suite is green. Never against the real %LOCALAPPDATA% data.',
  phases: [
    { title: 'Probe', detail: 'each acceptance measurement, driven against a throwaway campaign' },
    { title: 'Audit', detail: 'ratchets, laws, and the corpus numbers' },
    { title: 'Critic', detail: 'what is still unverified' },
  ],
}

const REPO = 'H:/coding/PathfinderGM/.claude/worktrees/gracious-ishizaka-a20934'
const CONTEXT = `Repository: ${REPO} (a git worktree; work only there). Read docs/stage-8-brief.md (acceptance section) and docs/stage-8-plan.md first. NEVER touch the user's real data: every live run uses override_settings(CAMPAIGN_DIR=<tempdir>) or PATHFINDER_GM_DATA pointed at a temp dir — tools/adversary.py and tools/probe_unsourced_effects.py show the pattern. Ollama at http://127.0.0.1:11434 is the model host; if it is busy, wait rather than skip. Report measurements, not impressions.`

const PROBE_SCHEMA = {
  type: 'object',
  properties: {
    measurement: { type: 'string' },
    passed: { type: 'boolean' },
    evidence: { type: 'string', description: 'the numbers and the lines from the turn log / transcript that show it' },
    defects: { type: 'array', items: { type: 'string' }, description: 'each with file:line where you believe the cause is' },
  },
  required: ['measurement', 'passed', 'evidence', 'defects'],
}

phase('Probe')
const PROBES = [
  { key: 'unsourced-heal', prompt: 'Run tools/probe_unsourced_effects.py (or reproduce it) against the real model in a throwaway campaign: "I drink my healing potion" with an empty satchel, three times. The measurement: no outcome with op heal/damage/buff/temp_hp carrying effects, and the PC hit points unchanged, in all three. Report each turn\'s intents and outcomes verbatim from the turn log.' },
  { key: 'feat-through-the-door', prompt: 'Build a character with a numeric feat (Weapon Focus on their weapon, Toughness, Improved Initiative) in a throwaway campaign; read the sheet via /api/sheet; assert the feat\'s bonus is present in the relevant number and that the term NAMES the feat as its source, the way "Ring of Protection" is named among AC terms (see tools/prove_build.py check_the_laws_hold). Then remove the feat from the sheet and assert the number moves back — law 2. Report the before/after numbers.' },
  { key: 'stacking', prompt: 'On a throwaway scene, give one character Weapon Focus, a masterwork weapon, and a +1 morale buff to attack, and read the attack terms from the sheet and from an actual attack roll\'s modifiers in the engine. Assert typed stacking per 1e: same named type takes the best; untyped/dodge/circumstance stack. Report the exact modifier list.' },
  { key: 'save-roundtrip', prompt: 'Save and reload a campaign whose PC has a document-backed feat; assert the bonus is applied exactly once after load (not doubled, not dropped), and that a snapshot/restore around a refused turn leaves it intact. Report the numbers before save, after load, and after a refused turn.' },
  { key: 'model-choice', prompt: 'Against the real model in a throwaway campaign: a character who DOES carry a healing jar says "I drink my healing potion"; a wizard with a prepared spell says "I cast magic missile at the thug". Assert the effects that land carry a source the engine resolved (the jar id, the spell id) and that no bare number was authored by the model. Report the intents and the sources recorded on the outcomes.' },
]
// One at a time, on purpose: every probe drives the same local Ollama, and two model
// runs at once stalled its queue for seven minutes in the places stage.
const probes = []
for (const p of PROBES) {
  probes.push(await agent(
    `${CONTEXT}\n\nYou are running ONE acceptance probe for stage 8: ${p.key}. ${p.prompt}\n\nWrite whatever script you need under the session scratchpad, never into the repository. Set PATHFINDER_GM_DATA or override CAMPAIGN_DIR to a temp directory before importing the app. Never run two model-driven probes at once. Fail loudly and specifically; a probe that could not run is a failure with the reason, not a pass.`,
    { label: `probe:${p.key}`, phase: 'Probe', schema: PROBE_SCHEMA }))
}

phase('Audit')
const audit = await agent(
  `${CONTEXT}\n\nAudit the ratchets and the corpus numbers after stage 8. (1) Run python -m pytest tests/test_three_laws.py tests/test_one_spatial_authority.py tests/test_stage7_refusals.py and any new stage-8 ratchet file, and report the result verbatim. (2) With an AST scan, count feat name-branches remaining in rules/engine.py and rules/sheet.py and list each with file:line; compare with the plan's claimed sixteen. (3) Count effect ops in rules/intents.py OPS that still accept a model-authored amount without a required source, and list them. (4) Run the whole suite and report the summary line. Numbers only; no adjectives.`,
  { label: 'audit', phase: 'Audit' })

phase('Critic')
const critic = await agent(
  `${CONTEXT}\n\nYou are the completeness critic. Below are five probe results and an audit. What is still unverified? A modality not run, a claim in the plan with no measurement behind it, a probe that passed for the wrong reason, a number in the audit that contradicts the plan. List each with what would settle it. Then give a one-paragraph verdict: ship, or not yet, and why.\n\nPROBES:\n${JSON.stringify(probes.filter(Boolean), null, 1)}\n\nAUDIT:\n${audit}`,
  { label: 'critic', phase: 'Critic' })

return { probes: probes.filter(Boolean), audit, critic }
