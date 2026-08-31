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

## Known and deliberately deferred

`rules/tables.py` is a hard-coded dict with no content overlay, unlike classes, feats and
spells, so a homebrew condition gets `condition.<key>` and nothing else: no recovery tag,
no mechanical fields. It survives `rest` today and will after stage 5. Not clearing an
unknown state on a nap is the safe default, but law 1 promises homebrew participates
unregistered, and here it does so only partly. Making `CONDITIONS` authorable is its own
stage; until then this is written down rather than assumed.
