# Stage 5 — one vocabulary

The plan of record for stage 5 of `docs/compliance-plan.md`. Written after a six-agent
reconnaissance of every string-matched state question in `rules/`, `play/`, `gm/`,
`world/` and `tools/`, and after the numbers below were measured rather than estimated.

## What is actually wrong

Not "forty branches should be tag queries". The fault is that **three vocabularies answer
the same questions and nothing checks they agree**:

1. the tag tree in `rules/states.py`;
2. boolean flags on the condition rows in `rules/tables.py` — `can_act`, `helpless`,
   `lose_dex_to_ac`;
3. 40 literal-key `has_condition("…")` branches, each carrying its own list.

Measured by AST census over the app (tests excluded): **102 call sites** of
`has_condition` / `add_condition` / `remove_condition` / `has_state`. Literal-string
first argument: `has_condition` 40, `add_condition` 17, `remove_condition` 5,
`has_state` 10. A further 45 literal keys sit inside loops at 10 sites. **107 literal
condition-key mentions in all**, against **12 tag queries — 10 of which ask the same
single query, `state.down`.** Nine of the eleven tag families `rules/states.py` ships
have zero readers.

The drift this produced, measured across all 31 shipped conditions:

- the `can_act` flag and the `state.unable` tag **disagreed on 3 of 31**: `fascinated`
  (tagged unable, flagged able), `helpless` (flagged unable, untagged), `nauseated`
  (flagged unable, and wrongly — 1e allows it "a single move action per turn" and the
  flag refused exactly that);
- `play/downed.py:state_of` returns `"fine"` — a normal turn — for **7 conditions that
  cannot act**: cowering, dazed, fascinated, helpless, paralyzed, petrified, stunned;
- `gm/watcher.py:_down` misses **5 of the 6 `state.down` conditions** at positive hit
  points: dead, dying, helpless, petrified, stable.

`lose_dex_to_ac` is *not* part of the fault: `Actor.ac` already reads it generically off
the rows for all 9 conditions that carry it. That is data driving a rule, which is the
shape we want. The fault is the hand-maintained duplicates nobody reconciles.

## Two live bugs this is the root cause of

**The petrified turn is a 502.** A petrified PC gets `state_of == "fine"`, so
`play/views.py` hands them a turn and the GM plans it — then `rules/engine.py`'s guard
raises `IntentError(check="legality")`, which regenerates rather than repairs. The turn
burns the retry loop and dies as a blank page. Required-op meeting hard-refusal is the
502 class `docs/design-contract.md` names; here it is caused by two authorities
disagreeing about one turn.

**The sap knockout wakes you up in an hour.** Non-lethal damage past the threshold writes
`unconscious`; `downed.state_of` collapses unconscious into `"stable"`; `resolve` then
ends the encounter, burns 60 minutes on the world clock and prints "You come round about
an hour later… on 9 hit points" to a character who was never below zero and is not
bleeding — leaving the non-lethal damage in place.

## The traps

Every one of these is the tempting implementation, and every one inverts a mechanic. They
are recorded because the naive version of this stage is worse than not doing it.

- **`can_act() -> not has_state("state.unable")`, alone, inverts three mechanics.**
  `rules/engine.py` reads `automatic = not defender.can_act()` to make a combat maneuver
  succeed *with no roll*; it also reads can-act to decide whether an attacker keeps
  swinging, and `Scene.conscious` reads it to count the sides still standing. Making
  `fascinated` unable therefore auto-grapples a distracted target, makes it unattackable,
  and ends the encounter with it standing up.
- **1e's maneuver clause is "immobilized, unconscious, or otherwise incapacitated"** —
  the `helpless` axis, which the rows already carry on five conditions and which
  **nothing read**. That is its owner, not can-act.
- **`has_condition("dead") -> has_state("state.down")` makes creatures unkillable.**
  The death and damage guards in `rules/sheet.py` are re-application guards; widening any
  of them to the family means a dying actor never crosses into dead. The only lawful
  conversion is the leaf.
- **A family-query `rest()` wakes the dead.** The fifteen names cut across five families
  and match none of them: `state.unable` contains `dead`, `state.held` contains
  `paralyzed`, `state.senses` contains `blinded` and `deafened`. Prefix-clearing any of
  them cures by sleeping what 1e says only a spell cures — and destroys the deliberate
  exhausted→fatigued downgrade three lines later.
- **`state.down` must stay wide.** The loot gate wants petrified and helpless in the
  family, on purpose. It is the sites that *delete* a creature that must narrow.
- **Tags are frozen in saves.** `ActiveEffect.from_dict` read them straight off the
  record, so a vocabulary change never reached a condition already saved, and no test
  would notice because every test builds its actors fresh.
- **Don't convert the toggle-identity sites.** The handful of `has_condition` calls that
  name one stance key come from a class document; rewriting them as
  `has_state("buff.stance.blood-armament")` hard-codes a class name into the engine and
  breaks any homebrew toggle, whose key self-tags as `condition.<key>`.
- **Don't convert `IMMUNITY_COVERS` to tag prefixes.** Immunity attaches to what an
  effect *declares itself to be*, not to the condition it produces — stage 3's recorded
  decision, and reversing it is what made 759 undead unkillable once already.

## Substages

### 5a — one authority on acting *(done)*

The vocabulary answers the capability question and the condition rows stop carrying a
second answer. `states.BLOCKS` maps a tag prefix to the ops it stops, so the vocabulary
can say **what** a state prevents rather than only whether it prevents everything;
`states.stops` reads the tags an effect actually carries, so a document that declares its
own `state.unable.*` tag participates without a table row.

Three questions get three owners: `Actor.can_act` (may I act now), `Actor.is_down` (am I
out of the fight), `Actor.is_helpless` (can I resist at all — 1e's maneuver clause, whose
flag had no reader). `Scene.conscious` stops conflating the first with the second; the
intent guard asks per op, so a nauseated character keeps the move action 1e allows them.

`ActiveEffect.from_dict` unions a condition's stored tags with what the vocabulary grants
today, so a vocabulary change reaches saved campaigns — unioned, never replaced, because
an ability document appends its own tags on top.

### 5b — one down-ness

Delete the second and third vocabularies: `play/downed.py:state_of` and
`gm/watcher.py:_down`, plus `gm/judgement.py`'s four-name tuple. `state_of` needs a fifth
answer for *unable but not on the hit-point track* — a petrified or paralyzed PC has no
turn to take **and no wake-up in an hour either**, so `resolve` must refuse with a
printable `Outcome`, never a legality raise and never the recovery path. Fixes both live
bugs above.

The departure sites that erase a creature narrow to the body leaves; `state.down` stays
wide for the loot gate.

### 5c — the by-name clears

`Actor.rest`'s nineteen names, `_op_heal`'s four, `downed.resolve`'s four,
`views.resurrect`'s five. Two axes, not one:

- **what ends it** — a fact about the condition, so it belongs in `states.TAGS` as
  `recovery.rest`;
- **why this actor holds it** — a fact about the *application*, not the condition:
  `unconscious` arrives from hit points, from non-lethal, from Intelligence 0 and from a
  sleep spell, and no key-indexed table can tell them apart. That is `source`, which the
  applicator already stamps, and remove-by-source is what `apply_nonlethal_state` already
  does.

Resurrection is the only caller entitled to remove `dead`; one shared list either breaks
it or lets cure light wounds raise the dead.

### 5d — the ratchets

An allowlist of the literal-key sites that are legitimately literal — the engine's own
mechanical writers in `apply_hp_state`, `bleed_out` and the survival fatigue ladder — in
the shape of `_CLOCK_SITES`, so a count cannot confuse a site being removed with one being
moved. Plus the two already marked stage 5: the dispel path's direct store edit in
`_STORE_EDITORS`, and unsaved `spawn_feet` in `_UNSAVED_SCENE_FIELDS`.

## What the adversarial review caught

Six defects, every one under a green suite, every one found by a probe rather than by
reading. Recorded because the pattern is now consistent enough to plan around: the suite
proves the change did what it said, and only a probe finds what it did *as well*.

1. **A maneuver against a corpse rolled a d20.** The automatic clause moved from
   `not can_act()` — eleven condition rows — to the `helpless` flag, which sits on five.
   `dead` and `stable` fell in the gap, so the player was handed a die to roll against a
   body on the floor and could fail. Now `is_helpless or is_down`.
2. **A fight where everyone was stunned vanished.** `sides_standing()` stayed at 2, so
   the "fight is over" branch was skipped, while `advance_turn` returned None, which the
   caller reads as the fight being over — the encounter ended with two live enemies
   upright, no XP and nothing printed. `advance_turn` now looks across rounds so the
   holds tick down. The *first* fix for this returned None just as silently, because the
   scan only ticks when it wraps and a fight starting from `turn == -1` never wraps on
   its first pass; the second probe caught it.
3. **`cast` in the guard was new 502 exposure.** The rule is right — a stunned wizard
   cannot cast — but `turn_schema` builds a `contains` the sampler cannot violate, so "I
   cast magic missile" forces the op that is about to be refused as a legality error and
   burns every attempt. Reverted to the three ops the guard always had. The vocabulary
   still says `cast` is stopped; making these refusals printable is stage 7.
4. **Nauseated creatures took attacks of opportunity.** Reactions and guards asked the
   general `can_act()`, so restoring the move action restored the swing with it. A
   spliced reaction never passes `validate`, so that gate was the only one. They ask
   `blocking_key("attack")` now.
5. **The tag union was a one-way ratchet.** Additions reached saved campaigns and
   removals never did, and the stale tag was written back on the next save. The
   namespaces the vocabulary owns are rebuilt outright; a document's own tags survive.
6. **A keyless blocking effect was invisible to `can_act`.** The predicate returned the
   effect's key, and a document-declared state need not have one, so the empty string
   read as "nothing stops you" — contradicting the promise `states.stops` makes.

A seventh finding was about the record rather than the code, and is worth keeping
straight: **three conditions is the count of the flag/tag *disagreement*, not the count
of conditions whose behaviour moved.** Sweeping 832 condition × hit-point pairs, old
formula against new, eight changed somewhere: `fascinated`, `nauseated` and `helpless`
from the disagreement, plus `dead`, `stable`, `paralyzed`, `cowering`, `dazed` and
`stunned` through `conscious` and `is_down` no longer being read off can-act. All are
correct by 1e — a paralyzed creature is still in the fight and is a coup-de-grâce target
— but "three changed" was the wrong sentence to have written.

One test was found pinning around a defect rather than pinning a rule:
`test_a_stunned_target_gives_a_four_bonus` added `stunned`, removed it again and
measured the base, because a stunned target used to succeed automatically and there was
no roll for the bonus to land on. It tests the +4 it is named for now.

## What the second adversarial review caught

A second pass over 5b–5d found eleven more, six of them mine and two of those worse than
what stage 5 set out to fix. Recorded in full because the pattern is the finding: this
stage was reviewed twice and the second pass was not redundant.

1. **`_wait_it_out` froze the fight around the player.** `Scene.advance` is EXPIRY ONLY
   by its own docstring — it runs no turns, fires no wards, drains no upkeep and never
   rolls the dying. Waiting a hold out with it put the player in a safety bubble:
   measured, a paralyzed character stood among three thugs for four rounds untouched
   while the burning cloud they were lying in lost four rounds of its clock for free.
   Every stun the player suffered became free. **This was worse than the 502 it
   replaced.** The turn is simply not theirs now: inside a fight nothing is skipped and
   the world takes its own turns through `advance_turn`, which is the door that fires.
2. **A clockless hold was a permanent campaign lock** — and clockless is `_op_condition`'s
   default when the GM omits a duration. Nothing ticked, no NPC could act, no removal
   path existed. Partly closed by (1), since the world now acts; **still open out of
   combat**, and recorded below.
3. **A document-declared hold was unwaitable.** `blocking_key` falls back to the effect's
   *name* when there is no key, and `downed` then looked the effect up *by key* — so a
   three-round hold read as permanent. The half of the first review's fix that made the
   case visible shipped without the half that lets it resolve.
4. **The 502 was still open at exactly 0 hit points.** `disabled` — a rung that hands out
   a turn — was tested before `held`, so all seven conditions reached the turn gate as
   playable whenever the character sat at 0 hp.
5. **Rebuilding owned tag namespaces destroyed document tags.** `_apply_ability_document`
   appends a document's tags in *any* namespace, so the first review's fix deleted them:
   a grant of `state.unable.trance` blocked actions in session and stopped after a
   restart. Reverted to the union; the cost — a withdrawn tag never reaches a save
   already on disk — is now stated in the code rather than hidden.
6. **A death during a skipped round was never reported.** `scene.bleeding` was an
   assignment six lines above the comment explaining why `hazards` beside it must be
   appended, so only the last of up to twenty skipped rounds survived.
7. **`spawn_feet` was persisted but never pruned**, and refs are recycled — so a departed
   archer's 120 feet was inherited by the next creature to take `c1`, which asked for
   `engaged` and was laid out 120 feet away. Harmless only while the field was dropped
   at every save; persisting it would have made the poisoning permanent.

Confirmed clean by the same review, exhaustively: the round-rollover rewrite agrees with
the old predicate on the first rollover for **every reachable (turn, length) pair**,
including `turn == -1` and a single-entry initiative order (2,646 cases, identical refs);
parking the turn pointer corrupts no order, re-grants no turn and loses no `acted`; and
both `recovery.*` families still reproduce the replaced literal lists verbatim.

## Known and deliberately deferred

**Open, measured, not fixed here** — carried into the stages that own them rather than
patched at the end of this one:

- **A clockless hold out of combat is still a lock.** In a fight the world now acts, but
  outside one nothing ticks and `_op_condition` mints `rounds=None` whenever the GM omits
  a duration. The real fix is a removal path and a refusal that offers one — stage 7.
- **`nauseated` is the `cast` problem already live.** It is `state.impaired`, so the turn
  is planned and `validate` then refuses `attack` and `check` as legality errors. Same
  buried-502 shape this stage declined to widen `cast` into. Stage 7.
- **`hp <= 0` still sits beside the tag query** at five of the sites 5b re-pointed, so a
  creature at exactly 0 hit points is standing and taking turns while `tidy_the_fallen`,
  `leave_behind` and the walking-dead prose cut all treat it as a corpse. Inherited, and
  the reason `Scene.conscious`'s docstring exists — but this stage claimed no two modules
  disagreed any more, and on this case they still do.
- **`petrified` and `helpless` are permanent scene ghosts.** They are `state.down` but not
  `state.down.fallen`, so after 5b narrowed the departure sites *nothing* removes them,
  and `rules/xp.py` still asks `hp > 0` — so petrifying the last enemy ends the fight
  with 135 XP unpaid and nothing said. That is the same bullet 5d claimed, still open for
  the down-but-alive half of the family.
- **`_retime`'s identity match is delivered by an equality-based `list.remove`.** Not
  reachable today because the dispel mutates `rounds_left` first, but the comment asserts
  a guarantee the one door does not provide.

`rules/tables.py` is a hard-coded dict with no content overlay, unlike classes, feats and
spells, so a homebrew condition gets `condition.<key>` and nothing else: no recovery tag,
no mechanical fields. It survives `rest` today and will after stage 5. Not clearing an
unknown state on a nap is the safe default, but law 1 promises homebrew participates
unregistered, and here it does so only partly. Making `CONDITIONS` authorable is its own
stage; until then this is written down rather than assumed.
