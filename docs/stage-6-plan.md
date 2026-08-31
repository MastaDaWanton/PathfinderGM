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

## What the reconnaissance added

Seven readers and seven probes, run against the real code and the twelve real campaigns.
The headline reproduced independently three times over: **20 of 20 live turns** in which
`_hp_state_effects` wrote a condition carried a tell that never mentioned it — 100%.

Findings that change the plan:

- **There was already a correct copy.** `_ward_tell` renders `'the guildhand is dead
  (hit points).'` — the only path in the app that got this right, so a ward kill told and
  a sword kill did not. 6a matched `_op_ability_damage`'s voice; consolidating the two
  renderers is 6b's, not a third one.
- **An ability that damages does not run the ladder at all.** Probed: a level-12 blood
  bender's Blood Spike Projectile took a thug to −22 of 13 against Con 13 — nine hit
  points past death — and wrote **no condition at all**. Not dead, not dying, not
  unconscious. That is a sixth site, and it is a creature that cannot be killed by that
  ability rather than merely a silent one.
- **`press_the_death`'s "already said it" guard is defeated by somebody else's death.**
  It accepts death language anywhere near a pronoun as evidence *this* actor's death was
  stated, so one enemy dying covers for another's.
- **`leave_behind` departs a corpse with nothing said** — it returns text for the dying
  and none for the dead.
- **`Outcome.player_visible()` has zero production callers**, while `gm/agent.py:959`'s
  docstring asserts the narrator is fed its output. A claim in prose that no code backs,
  which is the same failure this stage is about, one layer up.
- **81% of recorded tells (146 of 180) already name the player in the third person.** So
  the death tell naming them is the house convention, not a new hazard; the
  second-person conversion downstream is what handles it, and making death the one
  exception would be the drift.

Measured costs of the naive fixes, all three of which are now ruled out:

- flipping `claims=True` on the live path cuts **25 of 43** real consequence beats below
  forty characters — the beat is destroyed — and deletes **14 of 18** engine-authored
  lines;
- running `plain_tell` over the narrator's feed alters 38% of real tells, leaves 70 of
  212 still carrying digits, and destroys the player's own hit points and purse;
- the scrubber's worst pattern, the "escape" family, was wrong in **8 of the 9** times it
  fired in real play ("a soft sigh escaping her lips").

And the blind spot that makes 6c worth doing at all: **18 death and unconsciousness
assertions in shipped prose, 0 flagged.** Not one of the 44 patterns names a condition or
a state change.

## What landed

`cfa1d40` 6a — the hit-point ladder speaks, at all six sites (recon found a sixth).
`f5b454f` 6b — an ability that deals damage could not kill anybody; one phrasing table.
`7c312a1` 6e — the narrator ratchet, which was vacuously true and always had been.
`84151ef` — the player's own kill was being deleted off the page, and 6a made it worse.
`812b231` 6d — the dice popup stops handing over a roll made behind the screen.
`0a84462` 6c — the scrubber runs on the prose the player reads, because it knows the dice.
`0a84462`+ — a cure says the character came back.

Verified on the packaged build: `dist/PathfinderGM.exe` rebuilt, `prove_build` ALL CLEAN
over 21 checks, and the live path driven through `/api/say` against a copy of a real
campaign.

**Still open**, and honestly so — none of it is load-bearing for the laws, all of it is
measured:

- the tell canary still reads as full coverage and is 54% (34 of 63 `Outcome(`
  constructions), because it matches literal syntax rather than counting effect dicts;
- `apply_hp_state`'s `changed` list is appends-only, so waking up is silent — and the
  fix inverts the mechanic unless a direction field lands first;
- `found.title()` renders "Iron Clot (Dr 2/—)", and 37 of 49 blood-bending abilities
  fall through to a database row rather than prose;
- 594 spells put the raw `SAVE_DC_FORMULA` placeholder into the cast tell;
- `play/craft_views.py` writes a full dice breakdown to the transcript unstripped;
- `press_the_death`'s "already said it" guard is satisfied by somebody else's death, and
  `leave_behind` departs a corpse saying nothing.

## What the probes changed

Seven probes re-ran the readers' claims against live code. Several measurements did not
reproduce and are corrected here rather than carried: the "18 death assertions, 0
flagged" is 11 on a tight regex and 23 on a loose one, of which 3 are flagged; "20 claim
repairs across 261 turns" is 23 across 353; "85 application call sites" is 80; and
`_resolve_maneuver` is not "every ordinary route to death" — no shipped manoeuvre deals
hit-point damage at all.

Two probe findings landed as fixes in this stage rather than as notes, because both were
live: the ability path that could not kill, and the kill sentence being deleted.

Still open, measured, and belonging to later substages:

- **`_op_use_ability` emits no damage effect**, only `{"kind": "use_ability"}` — so the
  door is invisible to `_hurt_refs`, `_deaths_from`, the battle-joined check and the turn
  log. 6a gave it the ladder and the tell; the effect record is 6b's.
- **`_op_heal` is silent in both channels** — a cure that lifts `dying` and `unconscious`
  reports only `[('heal', None, None)]`, so nothing says the character came back.
- **`found.title()` mangles every ability name in its tell** — "Iron Clot (Dr 2/-)".
- **37 of 49 blood-bending abilities fall through to a database row**: "Blood Spike
  Projectile is a Control Blood 1 ability of the blood spike path; Masta has reached 0."
- **594 spells put the raw `SAVE_DC_FORMULA` placeholder into the cast tell**, and the
  suite cannot see it.
- **A sixth raw transcript door**: `play/craft_views.py` writes a full dice breakdown
  ("made (d20 12+8 = 20 vs DC 10)") straight to the page with no stripping.
- **The dice popup leaks the enemy's already-rolled hidden total** as the target number,
  before the player rolls — and the payload has no provenance to key a fix on.
- **`press_the_death`'s guard is defeated by somebody else's death**, and `leave_behind`
  departs a corpse saying nothing.
- **`apply_hp_state`'s `changed` list is appends-only.** The removals — `dying`/`stable`/
  `unconscious` cleared on death, `staggered` cleared, and both lifting when non-lethal
  heals back below the line — are never in it, so somebody who wakes up does so in
  silence. The trap is sharp and named: appending the removals **inverts the mechanic**,
  because the effect record carries no add/remove direction, so a lifted unconsciousness
  would be narrated as a fresh knockout. A direction field comes first, or not at all.
- **The tell canary reads as 100% coverage and is 54%.** Measured: 63 `Outcome(`
  constructions in `rules/engine.py`, 34 matched, 29 invisible — and all the hit-point
  sites are among the 29, because they pass `effects=effects`. It should count effect
  dicts reaching an Outcome, not literal syntax.
- **`_deaths_from` looks the actor up after the scene has swept it.** A turn that kills
  and leaves in one input — "I finish him and go" — departs the body before the death can
  be read off it, and the kill is never written. Narrowed by probe: `tidy_the_fallen` and
  `leave_behind` both no-op mid-encounter, so it cannot fire inside initiative.

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
