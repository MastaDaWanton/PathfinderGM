# Bringing the app into three-laws compliance

The programme derived from a ten-dimension audit of the whole codebase (162 findings:
53 silent-failure, 34 drifting-now, 23 blocks-authoring) and hardened by a six-lens
adversarial review that returned "needs-changes" on every lens. The laws themselves are
in `CLAUDE.md`; the reasoning is in `docs/design-contract.md` and
`docs/states-effects-tells.md`.

This file is the plan of record. It exists because the first draft contained three
changes that would have introduced new bugs while fixing old ones — that is what the
review was for, and the corrections are recorded here rather than remembered.

## What the review changed about the plan itself

**The green/red contradiction.** The draft said the sharpened law tests "will go red
immediately, exposing true scope" *and* "suite green at the end of every stage". Three
reviewers independently found this; both cannot hold, and nine stages of known-red makes
a new regression indistinguishable from an old one. **Resolution: every law test lands as
a ratchet, not a boolean** — `assert len(sites) <= N`, where N is the audit's own measured
count (6 clock decrements, 35 resolution-time raises, 40 literal-key `has_condition`
branches, 10 class-name sites, 6 unsaved Scene fields). The suite stays green, the number
is each stage's success criterion, and it only ever goes down. A stage that over-delivers
tightens N in the same commit.

**Not every channel is additive.** Law 2 says "one modifier funnel", and a test that
merely asserts a builder mentions `_buff_mods` pushes an executor toward
`sum(stack(...))` everywhere. In 1e, concealment, energy resistance, damage reduction and
temporary hit points are **max-not-sum** — blur 20% plus displacement 50% is 50%, not
70%. **The law test splits in two**: an additive set (attack, damage, AC, saves, skills,
initiative, CMB, CMD, ability score) that must read the funnel and end in `stack()`, and
a best-only set that must read the one store and must *not* sum.

**The funnel test's predicate is a false positive.** It asserts the source text of a
method contains `_buff_mods`. `initiative_modifiers` passes and deafened's −4 still never
arrives, because `_condition_mods("initiative")` is never read. **Replaced by a
parametrised behavioural table**: for every (kind, target) pair in the authoring
vocabulary, author a bonus and assert the number moves.

**The verification instruments are blind.** `tools/prove_build.py` — the packaged-build
prover CLAUDE.md requires — has zero checks that apply a condition, apply an effect,
advance a clock and assert expiry, or save and reload. Several defects here are
restart-only, so "run prove_build at the end" was not a verification claim. **Extending
prove_build is stage-1 work, not a closing step**, and it runs at the end of every
save-shape stage.

**Save-shape changes needed a prerequisite nobody had.** Details below; this became
stage 0 and is done.

## Stage 0 — done

Three commits, each verified, suite green.

- `04b1548` — `level_up` wrote `actor.abilities[ab] += amount` straight into the base
  score, which cannot reach 1e's retroactive rule. Measured on the shipped class at 20th
  level: 210 maximum hit points against 310 owed; the four +2 Constitution steps land at
  levels 5/10/15/20 against 10/20/30/40 Hit Dice, so the debt is 10+20+30+40 = **100 hit
  points, one third of the character's total**. Growth now goes through
  `Actor.grow_ability`. `level_up` also called `actor.rebuild_pools()` behind a `hasattr`
  guard and the method had never existed: nine levels in one session left a rage pool at
  5 rounds where its formula said 25, and a reload silently corrected it, which is why it
  was never caught.
- `a4b6bea` — "no model authors a number" had no enforcement. `spawn.count` was bounded
  and its neighbours were not: `give.count` could mint 1,000,000 gp, `forage.hours` could
  drive the loop for a year, `attack.iteration` indexed inside resolution and raised there
  as a 500. `dice.parse` bounded the dice and not the constant, so `1d6+999999` read as
  plausible. All now clamp (the `rules/dc.py` choice — the model meant "a lot", the engine
  decides how much) and refuse only non-numbers, naming the field.
- `36a0eb2` — **the most dangerous defect found.** `_resume` wrapped `Campaign.load` in a
  bare `except Exception`, renamed the save, and returned None; `current()` answers None
  with `_begin`, which saves immediately. Any load error cost the player their campaign
  and wrote a fresh character over its name, silently. And `save_version != SAVE_VERSION`
  made every shape change unshippable — bumping it would have handed all twelve real saves
  to that same path. Both fixed; verified by loading copies of all twelve real campaigns
  (12 loaded, 0 failed, nothing renamed or created). This is the prerequisite for every
  later stage that changes what a save holds.

Both defect-pinning tests found here asserted the *broken* behaviour, one with a docstring
stating the opposite of its own assertion. A test that pins a defect protects it.

## The remaining stages

Each ends with the suite green, a commit naming its measurement, and — for any stage that
changes a save — a round-trip over copies of the twelve real saves asserting no derived
number moved except the ones the stage names.

**Stage 1 — sharpen the instruments. DONE** (`56929d9`, `dda40d7`, `bf1d827`).
The gate first: the suite failed one run in five, diagnosed by reproduction as unseeded
dice in a fixture that hands the round to an NPC swinging at a 9-hit-point rogue — not
the CAMPAIGN_DIR leakage the review assumed, though that is fixed too. Five of five
green after. Then the four turn-costing refusals pulled forward. Then the law tests:
the funnel test became behavioural (the substring version passed `initiative_modifiers`
while deafened's −4 never arrived), the ticker test grew from one clock to all five, the
applicator gained the test law 2 never had (18 direct mutations against 6 applicator
calls), the best-only channels are pinned so nobody sums concealment, six unsaved Scene
fields are named, and `prove_build` now wears a ring through the packaged exe, restarts
it, and asserts the effect survived. Ratchets are named allowlists, not counts, so they
tighten themselves.

*Superseded plan text follows, kept for the reasoning:* Law tests become ratchets with
the audit's counts.
Funnel test becomes the behavioural table. Additive/best-only split. Add the missing
applicator test (nothing outside `apply_effect`/`remove_effects`/`tick_effects` may touch
`.effects`; measured today: 2 applicator call sites against 15 direct mutations). Add the
refusal-pattern ratchet. Widen the engine-names-no-class-ability sweep (the two-file
version reads too little; widened it finds 10 sites). Add the dataclass-field-walk
persistence test — 6 Scene fields went unsaved unnoticed. Extend `prove_build` to apply an
effect, restart the exe against the same data directory, and assert it survived.

**Stage 2 — one funnel. DONE** (`6e525fe`, `a51259e`, `3d7df25`).
`bonus_type` was dropped between the author and the roll — 772 of 1,145 shipped
modifier specs carry a type that does not self-stack, and every timed bonus entered
untyped, so two alchemical teas were +4. `ability_mod` effects land on the SCORE now
(a +2 belt was worth +2 where raising 12 to 14 gives +1: every belt and headband was
double), and `hp_max` became derived in the same commit, because otherwise a
buff→damage→expire→heal sequence minted hit points — the shape law 2 forbids, created
by the fix. Concealment reads the funnel; speed and touch AC joined it once their
content was typed, which exposed fourteen specs whose note said "armour" and whose
type said "untyped". Three things the tests caught that the design missed: the level-up
floor broke under derivation (Con 3 made levelling *cost* hit points), `ability_score`
read the funnel without `stack()`, and `set_hp_max` ran before `classes.apply` — which
sets `hit_dice_per_level` — so five of the user's twelve characters gained hit points
on load (Thor 23→37) until it moved. Verified: twelve saves load, none moved.

*Superseded plan text follows, kept for the reasoning:* `ability_score()` becomes the
funnel point for `ability_mod`
bonuses and `ability_mod()` becomes pure derivation — **one shape, not both**: the draft
named both and would have applied every belt twice. This stage must also land the derived
`hp_max` (audit finding 135), because once Con buffs reach `ability_score` the existing
`_apply_con_change` before/after asymmetry goes live and a buff-damage-expire-heal
sequence permanently mints hit points — the "added and hopefully subtracted" shape law 2
forbids, created by the fix. `concealment` and `add_buff`'s missing `bonus_type` join
here. **Speed and touch AC need their content typed first**: 69 shipped speed specs carry
no bonus type and would all stack (+80 where 1e gives +30); 36 of 60 non-deflection AC
specs are untyped crafted armour. Type the content, then move the reader.

**Stage 3 — defence channels become effects. DONE** (`db660da`, `a5f6e18`).
The four became effect kinds with the field names as views, and the store shape and save
shape changed in one commit with an idempotent migration that runs *after* the effects
rebind. A potion of fire resistance works: 123 spells and 13 magic items authored a
defence that `_spec_to_intents` had no branch for, so the dose was spent and nothing
happened. Speed gained the consumable branch its stage-2 reader was waiting for. The
immunity gate went on the OPS and never on `add_condition` — that applicator writes
hit-point death, so gating it would have made 759 undead unkillable — and immunity
attaches to an effect's descriptor, because 469 creatures are immune to sleep and sleep
immunity does not stop unconsciousness from hit-point loss. Three bugs found on the way:
the defence identity collapsed DR 10/silver and DR 3/— into one record, the DR reader
double-counted once `reductions` became a view, and `PARAM_ALIASES` renamed `against` to
`opposed_by` for *every* op — a landmine for any op declaring that word, now scoped.
Verified: twelve saves, no drift, no duplication.

*Superseded plan text follows, kept for the reasoning:* defence channels become effects,
with the save shape changing in the same commit. The draft split the store change (stage 3) from the file change (stage 5),
which would ship two builds whose memory and disk disagree. One idempotent migration
converts legacy defence fields to infinite effects *after* the `a.effects` rebind.
**Immunity gates the ops, never `Actor.add_condition`** — the applicator is also how
`apply_hp_state` writes dead/dying/unconscious, and gating it would make 749 undead
creatures unkillable. And 1e attaches immunity to an effect's *descriptor*, not to the
condition it produces: sleep immunity does not prevent unconsciousness from hit-point
loss.

**Stage 4 — one clock and one ticker** (split from the draft's single stage, which was
three). 4a: one `Scene.advance(minutes)` owning the six clock sites. 4b: one ticker plus
expiry tells — four of five tickers discard their "what ended" lists, so effects expire
in combat with nothing said. 4c: the store migrations (guards, wards, manifestations,
compulsions, pool cooldowns), each with its save shape.

**Stage 5 — one vocabulary. DONE** (`51f7199`, `b80b239`, `bf9b2b4`, `96d67cc`;
`docs/stage-5-plan.md` is the record). The estimate held exactly — the AST census found
40 literal-key `has_condition` branches against 12 `has_state` queries, and ten of the
twelve asked the same single query, so nine of the eleven tag families had no readers.

It was three questions answered by five authorities, not one question answered twice:
"may I act now" (`can_act`, per op, since 1e's incapacities are not all total), "am I out
of the fight" (`is_down`) and "can I resist at all" (`is_helpless` — 1e's maneuver
clause, whose flag sat on five condition rows with **no reader anywhere**). Two live
player-facing bugs fell out of the disagreement: a petrified character was handed a turn
the engine then refused as a legality error, which regenerates rather than repairs and
reached the player as a 502; and `state.down` meaning both "lootable" and "a body on the
floor" meant a petrified enemy at full hit points was deleted from the scene as a corpse.

What the tempting implementation would have cost, all measured: `can_act ->
not has_state("state.unable")` alone auto-grapples a fascinated target, makes it
unattackable and ends the encounter around it; a family-query `rest()` raises the dead,
cures paralysis and deletes blindness. Recorded in the tests rather than in prose.

`cast` belongs in the intent guard by the rules and was deliberately left out: the turn
schema forces the op the guard would refuse, which is the buried-502 shape. Stage 7.

**Stage 6 — severed tells. MOSTLY DONE** (`cfa1d40`, `f5b454f`, `7c312a1`, `84151ef`,
`812b231`, `0a84462`; record `docs/stage-6-plan.md`, which lists what is left).

All four symptoms were one thing. The tell for a killing blow was "the thug takes 30
slashing damage." — the condition went into `effects` and never into `tell`, so across
the twelve real campaigns 27 hit-point states were applied and ZERO named. The narrator
was never told anybody died, which is exactly why a repair reached past the tell to do
hit-point arithmetic and press the kill onto the page afterwards.

Two live bugs underneath: an ability that dealt damage never ran the ladder at all (a
blood bender took a thug nine hit points past its death line and wrote no condition), and
`cut_dead_men_walking` was deleting the player's own kill sentence — which 6a made worse
before the fix went in beside it.

Law 3's ratchet was vacuously true and always had been: `.effects` appears zero times in
`gm/`, because both reach-pasts spell it `getattr(o, "effects", …)`.

The scrubber now runs on the prose the player reads. Flipping the flag was the wrong fix
and the measurements say why — blind, it cuts 25 of 43 real consequence beats below forty
characters and deletes 14 of 18 engine-authored lines. `find_outcome_claims` is shown what
the outcomes structurally establish instead, so reporting survives and invention does not.

**Stage 7 — refusals.** 35 resolution-time raises against 13 refusal Outcomes. Classify
each: a raise is correct only when a *different* intent would have worked.

**Stage 8 — every number points at a document.** Shipped 2026-09-03
(`docs/stage-8-plan.md`, the record). Planned as "feats as documents"; the recon found
the same law broken from the model's side — `heal 1d8+1` for a potion nobody held, the
prompt's own worked example handed back — and the stage became one principle on two
surfaces. Provenance is `Intent.origin`, stamped by `Engine.validate(raw, origin=...)`
after parse and refused at parse if the model writes it; the seven amount-ops (and the
four outliers the maps found: save-branch dice, guard amounts, pool gains, compel's
penalty) are refused at validate without a stamp and are not offered to the sampler at
all, with a bestiary creature's fight turn as the one named exception; the jar, the
coating, the cheat clerk and the tests stamp; hazards are a rule document
(`content/rules/hazards.json`) the model cites by slot. Feats: forty documents in
`content/feats/mechanics/`, read live through `_buff_mods` like worn gear with a roll
context for `scope`/`when`/`choice`; the hand-written table, `power_attack_terms`,
`has_feat`, the suffix and substring matches are gone; `_NAMED_IN_ENGINE` for the
sheet is 1. The count in the sentence above was wrong both ways: fourteen applied, two
read by nothing, three families the count missed.

**Stage 9 — class-name strings out of the engine.** "control blood", Power Attack through
the intent schema, Swift Strikes in the attack op, starting-kit class tables.

## The destination, and the honest gap

The scalability lens's warning is recorded here because it is the thing most likely to be
forgotten: after all these stages the engine is lawful and **the corpus is still inert** —
25,464 shipped effect specs, 3,415 of them `narrative`, 3,015 authored `duration` blocks
no executor reads, 7,138 `sense` specs with no consumer. Compliance is not the same as
capacity. A later programme has to make the authored content executable, or the app will
be beautifully lawful and no more capable than it was.
