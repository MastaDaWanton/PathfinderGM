# Attack riders: what rides a printed hit

## The defect, as measured

Found by the 0.2.24 monster-attacks lane and measured 2026-10-30 over
`content/bestiary/compiled.json`. "bite +3 (1d6+1 plus disease and paralysis)" compiled into
an attack carrying `riders: ["disease", "paralysis"]`, and nothing ever fired the riders.
There were 1,036 rider words across 161 distinct riders:

| rider | count |
|---|---:|
| grab | 326 |
| poison | 191 |
| disease | 64 |
| bleed | 42 |
| energy drain | 40 |
| trip | 36 |
| burn | 32 |
| paralysis | 31 |
| distraction | 20 |
| stun | 12 |
| attach | 10 |
| pull | 7 |
| push | 4 |
| bull rush | 3 |

The only one that did anything was a swarm's distraction, wired the same day
(`Engine._distraction`). So a ghoul paralysed nobody, a giant spider's venom was only a
bite, a rat swarm's filth fever infected nobody, and a wolf tripped nobody.

The reader also dropped riders without a word. Any "plus" piece that began with a digit
and was not a damage type was thrown away:

- 26 "plus 1d8 bleed";
- 16 ability damages and drains ("plus 1d4 Con drain", "plus 1d2 Str");
- "plus 6 fire" (the magma dragons' constant extra damage);
- "1d4 nonlethal", "7 precision" and similar.

## The rules (Bestiary, Appendix 3, Universal Monster Rules; aonprd.com/UMR.aspx)

- **Grab**: "If the creature hits with the indicated attack, it deals the normal amount of
  damage and tries to start a grapple as a free action without provoking an attack of
  opportunity." It gets +4 on the check. It works "only against opponents of the same size
  category or smaller" unless the block says otherwise (B1 p.301).
- **Trip**: "a free action without provoking an attack of opportunity ... If the attempt
  fails, the creature is not tripped in return" (B1 p.305).
- **Pull / Push**: "a free combat maneuver check", with the distance the block's, "only on
  creatures of a size equal to or smaller than" the creature. The creature moved "do[es]
  not provoke" (B1 p.303).
- **Poison / Disease**: the effects "including its save, frequency, and cure, are included
  in the creature's description". The DC is "10 + 1/2 [the] racial HD + [the]
  Constitution modifier; the exact DC is given in the creature's descriptive text"
  (B1 pp.302, 299).
- **Afflictions** (Core Rulebook pp.555-557, aonprd.com/Rules.aspx?ID=417):
  - "All afflictions grant a saving throw when they are contracted. If successful, the
    creature does not suffer from the affliction."
  - Onset: "the affliction's effect does not occur until after the onset period has
    elapsed and then only if further saving throws are failed."
  - Frequency is "how often the periodic saving throw must be attempted".
  - Cure is "commonly ... a number of saving throws that must be made consecutively".
  - Each further dose of a poison "extends the total duration ... by half" and adds +2 to
    the DC.
- **Paralysis**: one save, which "does not permit saving throws each round". The length is
  the block's: "specific duration varies by creature" (B1 p.302).
- **Bleed**: damage "each round at the start of the affected creature's turn", which "can
  be stopped with a successful DC 15 Heal skill check or through the application of any
  magical healing" (B1 p.298).
- **Burn**: fire damage on the hit, then a Reflex save "or catch fire", burning for 1d4
  rounds. Putting it out takes a full-round action with +4 for dropping and rolling
  (B1 p.298).
- **Attach**: "The creature is grappled, but the target is not" (B2 p.294).
- **Constrict**: bludgeoning damage "when it makes a successful grapple check" (B1 p.298).
- **Blood drain**: Constitution damage "if it grapples a foe" (B2 p.294).
- **Energy drain**: negative levels, plus 5 temporary hit points each to the drainer, and a
  Fortitude save 24 hours later (B1 p.299).
- **Type immunities**, all from the Bestiary:
  - undead (p.309): bleed, disease, paralysis, poison, stunning, energy drain, ability
    drain, and damage to physical scores;
  - constructs (p.307): bleed, disease, paralysis, poison, stunning. Their ability-damage
    and energy-drain line is from the book; the page aonprd served did not show it.
  - oozes (p.308): poison, sleep, paralysis, polymorph and stunning;
  - plants (p.309): the same, plus mind-affecting effects.

## Prior art

Combat Manager (Kyle Olson) parses the affliction format in one regular expression,
`CombatManagerCore/Affliction.cs`, `FromSpecialAbility`. It reads:

- name and cause;
- save type and DC;
- onset, as a die and a unit, or "immediate";
- frequency, as a count and a unit, with an optional "for N units" limit;
- the effect: ability damage, a second ability damage, "X for N units", or other text;
- the cure.

`attack_riders.afflictions` keeps that shape field for field. It goes further in two ways.
It reads an effect of several pieces one piece at a time. A piece it cannot read goes into
`unread` instead of failing the whole effect.

## What was built

- **`rules/attack_riders.py`** reads each rider word into a document. It reads Special
  Attacks ("paralysis (1d4+1 rounds, DC 13, elves are immune to this effect)", "grab
  (Huge)", "burn (1d6, DC 14)", "constrict (1d8+6)") and Special Abilities (the
  affliction entries, "Stun (Ex) ... DC 23 save or be dazed for 1 round"). With no
  printed DC, the document names the UMR formula's ability, and the engine works the DC
  out from the live body. With no printed definition, nothing is invented: the document is
  `kind: unsupported` with its `why`.
- **The compile** stores the documents on each attack as `rules` (COMPILER 3). The record
  is now hashed over `special_attacks` and `special_abilities` too. A block read live
  (homebrew, templated) gets the same documents on the hit that needs them.
- **The reader** (`statblock_attacks._amounted`) carries "plus 1d8 bleed" as `bleed` with
  `amounts`. A piece that is no rider word keeps its whole print and is reported. "plus 6
  fire" is extra damage.
- **`Engine._printed_riders`** applies each document on the hit, through doors that already
  exist:
  - grab, trip and bull rush: `_resolve_maneuver`, with the rider's +4 as a named term and
    no backfire;
  - pull and push: a free CMB check, then `_shove`;
  - attach: the grappled condition on the attacker, with its holder written;
  - constrict and blood drain: on the hold just won;
  - paralysis and a defined stun: one save, then the condition for the printed length;
  - bleed: the `bleed` condition run by the periodic executor. It does not stack: a
    second bleed replaces the first only when it is worse.
  - burn: fire damage, then a Reflex save, then the `burn` op's clinging fire with the
    UMR's +4 to put it out;
  - ability damage and drain: the `ability_damage` op;
  - poison and disease: `_rider_affliction`.
- **Afflictions are an `ActiveEffect`** of kind `affliction`, tagged
  `state.afflicted.poison` or `state.afflicted.disease`. Its `periodic` entry is run by the
  one executor (`Actor.run_periodic` calls `Actor._afflicted`):
  - the onset and frequency are counted in rounds (a day is 14,400). `Scene.advance` gives
    a stretch of time its rounds, so a fever keeps its course across a night or a
    twelve-day wait;
  - played rounds fire poisons;
  - each due save is rolled with the save's `against` context (antitoxin's +5 reads it);
  - consecutive successes cure; a counted frequency runs out;
  - while the body is immune (delay poison), it is held and not spent.

  The clock, count and streak ride the effect's payload, so they survive a save and load.
- **Immunities** are asked through `states.immune_to`, which checks the printed list, then
  the type's bundle by tag (`TYPE_BUNDLES`). Physical ability damage on undead is asked
  through `states.ability_harm_refused`. "ooze traits" and "plant traits" gained rows:
  before, a gray ooze could be poisoned.
- **Every application is told.** A rider that is not applied returns a
  `rider_unsupported` effect with its reason and no tell, because nothing happened.

## Counts after (2026-10-30)

There are 1,107 rider documents, 71 more than before, because the dropped riders are
carried now.

**Applied (709):**

| kind | count |
|---|---:|
| manoeuvre: grab | 326 |
| manoeuvre: trip | 36 |
| manoeuvre: pull | 7 |
| manoeuvre: push | 4 |
| manoeuvre: bull rush | 4 |
| affliction: poison | 128 |
| affliction: disease (one of them "plus red plague") | 37 |
| bleed | 60 |
| burn | 32 |
| save condition: paralysis | 27 |
| save condition: stun | 1 |
| distraction | 20 |
| ability damage and drain | 16 |
| attach | 10 |
| blood drain | 1 |

**Reported, not applied (398):**

| reason | count |
|---|---:|
| energy drain: negative levels are not applied (see below) | 40 |
| a poison on a made weapon: the dose is gear | 30 |
| natural poison with no printed definition | 30 |
| disease with no printed definition | 28 |
| another unsupported rider (named curses, confusion, spores, "7 precision", ...) | 270 |

`tests/test_attack_riders.py` holds the unsupported count at 358 or fewer.

## Not done, on purpose or not yet

- **Energy drain.** A negative level moves eight numbers at once, and `effectspec`'s
  `negative_level` type records the decision not to apply seven of them. The rider asks
  the immunity and reports. Applying negative levels whole is its own piece of work, and
  so is the drainer's 5 temporary hit points.
- **Maintaining a grapple — BUILT 2026-11-01** (fix/combat-grapple-abilities). The grab
  writes the hold onto the held one's condition (`hold_weapon`, `hold_bonus`, `hold_then`);
  on the holder's later turns `Engine.grapple_turn` rolls the maintaining check (CMB +5,
  the grab's +4, against CMD) and a kept hold deals the seizing attack's damage, or the
  constrict in its place; a failed check ends it. The held one breaks it with `escape`
  (CMB or Escape Artist against the holder's CMD), and `_grapples_settle` / `Scene.
  end_encounter` end it when the holder is down, dead, gone or moved apart, or the fight
  ends (tests/test_grapple_held.py). Still not done: blood drain fires on the winning hit,
  where the UMR says "at the end of its turn"; the -20 hold that keeps the creature itself
  ungrappled; and the maintaining check's other options (move, pin, tie up) — a kept hold
  always deals damage.
- **CMB.** A creature's manoeuvre uses `flat_attack`, as every stat-block manoeuvre always
  has. The printed CMB ("CMB +6 (+10 grapple)") is stripped at import.
- **A poison dose on a made weapon** ("mwk kukri (1d4 plus poison)", 30). The dose is in
  the gear line, and coating from gear is not read.
- **Afflictions defined by reference.** "disease (DC 15)" on a ghoul variant means ghoul
  fever at that DC. The compile reads one block at a time and does not borrow the base
  ghoul's entry.
- **Cures by spell.** Neutralize poison and remove disease are narrative documents in the
  spell content. Nothing ends `state.afflicted.*` by spell yet. The applicator
  (`Actor.end_affliction`) is ready for one.
- **Whether the contraction save counts toward a poison's limit.** No primary sentence
  could be confirmed. This reading lands the first effect on the failed contraction save
  and counts it as the first of "1/round for N rounds".
