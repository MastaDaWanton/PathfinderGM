# A manoeuvre does what its tell says

*Design record, 2026-09-27. The code is `rules/tables.py` (MANEUVERS: `outcome`, `sheet`,
`short`/`blocked`, `tricks`, `fastened_cmd`) and `rules/engine.py` (`_resolve_maneuver`,
the `_outcome_*` applicators and `_MANEUVER_OUTCOMES`, `_let_go`, `_into_hands`,
`_steal_choice`, `_push_line`, `Scene.out_of_hand`, the attack legality check, the
ground branch of `_op_give`). The tests are `tests/test_maneuver_outcomes.py`. It sits on
the tells-by-name work (`maneuver_text`, `tests/test_maneuver_tells.py`).*

## The report

Reading `MANEUVERS` beside `_resolve_maneuver` on the tells-by-name branch: seven of
the ten manoeuvres told the narrator an outcome nothing in state carried.

| manoeuvre | the tell said | what state held |
|---|---|---|
| disarm | "the thug drops one carried item" (by 10: "everything held in both hands") | the sap still `equipped`, still on `weapons`, swingable |
| disarm, failed by 10 | "drops the weapon used for the disarm" | still in the hand; said even of a fist |
| steal | "takes an object Kesst Vayr is carrying" | nothing moved |
| bull rush | "pushed back 5 feet", "pushed another 10 feet" | `Scene.positions` untouched |
| drag | "dragged 5 feet" | untouched |
| reposition | "moves the target to another square within reach" | untouched |
| overrun | "moves through the target's space" | untouched |
| dirty trick | "blinded, dazzled, deafened, entangled, shaken or sickened for 1 round" | `dazzled`, until dismissed |

The narrator is fed tells and nothing else (the third law). Each row was prose asserting a
fact the next beat could not find: the "disarmed" thug swings the same sap, the "stolen"
purse pays for his next drink, the map shows both men where they started, and a model
told six conditions is free to narrate a blinding no roll will ever feel.

## The rules, from the books

Primary text: aonprd.com, Combat Maneuvers (Core Rulebook pp.198-201; APG for drag,
dirty trick, reposition and steal).

- **Disarm.** "Your target drops one item it is carrying of your choice (even if the item
  is wielded with two hands)"; by 10 or more, "the items in both hands"; failing by 10,
  "you drop the weapon that you were using"; unarmed, "you may automatically pick up the
  item dropped". **Where it lands the book never says.** Greater Disarm's "lands 15 feet
  away" implies the plain one stays at the wielder's feet; no FAQ was found.
- **Steal.** One item "neither held nor hidden in a bag or pack". Loose things (brooches,
  necklaces) are easy; fastened things (cloaks, sheathed weapons, pouches) give +5 CMD;
  armour, backpacks, boots, clothing and rings cannot be taken; held items are the
  disarm's. The target knows at once unless the thief has Greater Steal.
- **Dirty trick.** One of blinded, dazzled, deafened, entangled, shaken or sickened, for
  1 round plus 1 per 5 over; the target can spend a move action to remove it. Who picks
  is not stated; the examples read as the attacker, subject to the GM.
- **Bull rush** 5 ft plus 5 per 5 over, not into a solid square; a creature in the way
  forces a second check. **Drag**: both move 5 ft (+5 per 5), stopping at a creature in
  the way. **Reposition**: the target moves 5 ft (+5 per 5) and stays within reach but
  for the last 5 ft; the attacker stays. **Overrun**: success moves the attacker through
  the target's space; by 5, the target is prone.

## How others model it

- **Foundry VTT pf1**: a manoeuvre is an attack roll against CMD and every consequence is
  the GM's. No issue on its tracker proposes, adds or rejects automating a drop, a
  transfer or forced movement. That is the shape this engine had — and it only works
  with a human at the table to do the rest.
- **Owlcat's Pathfinder: Kingmaker / Wrath of the Righteous** changed the rule: disarm is
  a timed "cannot use weapons" condition, 1 round +1 per 5, and nothing is dropped.
  **Refused here.** The weapon returning on its own is not 1e, and the props ledger
  already carries a thing lying on the ground (the sunder's fragments, 2026-09-18).
- **ROM 2.4** `fight.c:disarm()` puts the weapon on the room's floor (`obj_to_room`), never
  into the attacker's hands, and an NPC that can see it picks it straight back up;
  `do_steal` takes only an item with no wear location into the thief's inventory. The
  drop and the steal follow ROM. The NPC's pick-up is docs/creature-rearms.md, priced by 1e.
- **NetHack's** bullwhip puts a snatched weapon under the monster, at your feet or in
  your pack by skill; a branch where the snatched weapon hit you is still in the source
  under `#if 0`, which is to say tried and abandoned.
- **Zones without a map** (Fate's War of Ashes, 13th Age): forced movement is a whole
  zone or nothing; a 5-foot push breaks engagement without crossing a zone. No published
  table turns feet into zones.

## What the engine does now

Every row of `MANEUVERS` whose `effect` is a claim carries a `condition`, the sunder's
`damages_item`, or an `outcome` naming an applicator in `Engine._MANEUVER_OUTCOMES`. The
applicator changes state through a door that already existed and returns the sentence
for what it did, so the tell is written from the change:

- **drop** (disarm): `_let_go` takes the item off `weapons`/`goods`/`shield`, empties the
  hand to `unarmed` (no free draw — the sunder's destroyed branch draws the next weapon,
  a drop does not, because a draw is an action the tell would have to claim) and puts it
  on the props ledger at this spot, still its owner's, named for its owner ("the thug's
  sap") so two thugs' saps are two records. By 10, the weapon and a held shield (a
  buckler is strapped on and stays). Unarmed, the attacker picks it up. The backfire
  drops the attacker's own weapon, and says nothing when there was only a fist.
- **take** (steal): the item is chosen before the roll, because a fastened one is +5 CMD.
  Loose goods, pockets and a neck slot first; then a sheathed weapon, the coin purse (all
  of it) or a cloak. Held or worn-close items are refused before any die is handed over,
  naming the disarm. The thing moves into the thief's carry with a props record
  `held_by` the thief and `owner` the victim.
- **trick** (dirty trick): the intent's `trick`, validated at parse against the six
  (default dazzled), applied with `rounds = 1 + margin // 5`; the tell names that one.
- **push / drag / shift / pass**: `_push_line` walks square by square and stops at a wall
  or a body; the tell's feet are the feet actually moved ("pushed back only 5 feet before
  the way is blocked"). Drag backs the attacker off and the target follows no further
  than it went. Reposition honours the intent's `square` when it keeps the rule, and
  otherwise takes the nearest open square in reach. Overrun lands the attacker on the far
  side and never in the target's square. None of it provokes (no `_op_move`, so no
  `_reactions_before`). With no map the zones are the only record: a bull rush with the
  player on either end breaks melee (`engaged` → `near`); the rest keep their zone. In
  play this branch is not reached: the first blow of any fight lays a map.

And the doors the outcomes needed:

- **The attack legality check** refuses a weapon whose owner's record lies on the ground
  or in somebody else's hands, *before* the carried-list test — that test is skipped when
  the list is empty, so a thug disarmed of his only weapon could name it and swing. It
  also refuses a weapon sundered to pieces, which stayed on `weapons` at full damage.
- **Picking a thing up** (`_op_give` from the ground) carries a whole record as what it
  IS (`from_`), not as "the thug's sap", so it can be swung; a picked-up weapon is in the
  hand. Fragments stay fragments.
- **`from_dict` copies** `weapons`, `feats` and `abilities`. `instantiate` shallow-copies a
  template, so every thug shared one list: one thug's dropped sap left every thug in the
  run holding only a dagger, and `_op_give`'s `weapons.append` had been arming the whole
  bestiary whenever one creature was handed a sword.
- The natural-weapon push/pull rider (`_shove`) is the same `_push_line` now, one copy of
  forced movement rather than two; it had checked anchors only, so a Large body's second
  square did not block.

## Still open

- ~~**NPCs never pick their weapon back up.**~~ Closed 2026-09-27 on branch
  `creature-recovers-weapon`: the engine re-arms a disarmed creature first (pick it up
  within reach, which provokes; else draw a carried weapon; else fists). See
  docs/creature-rearms.md.
- ~~Manoeuvres have no reach check.~~ Closed 2026-09-28 by the maneuver-reach work
  (`position.out_of_reach`, tests/test_maneuver_reach.py): a blow or a manoeuvre from
  further than the attacker reaches is refused, and the square is named.
- Steal's "at least one free hand" and Greater Steal's unnoticed theft are not modelled;
  nor is removing a dirty trick early as a move action.
- A 1-round condition ticks at the top of the round (the one ticker), so a target earlier
  in initiative than its attacker never acts under it. Every timed effect shares this.
- The bull rush's second check against a creature in the way is not rolled: the push
  stops there and says so.

## Live runs, 2026-09-27

A scripted fight through the real `/api/say` loop (gemma-4-12B, the fixture world, a
tavern brawl with Borin Lyraxys), eleven lines, each turn's tells set beside the state.

- **Run 1** reached none of the new applicators: "grit in his eyes to blind him" came back
  as `{"trick": "blinded"}` with no manoeuvre and was rolled against AC; "I shove him back
  hard" filed `bull_rush` as the weapon, was refused, and was retried as a plain swing;
  "I grab him by the collar and drag him" came back as drag and was overruled into a
  grapple, because drag and reposition had no cue in `judgement.MANOEUVRE_CUES`. All
  three fixed (normalize_attacks, the cue table).
- **Run 3**, after those fixes: the grit was a dirty trick and the shove a bull rush,
  both straightened in code. Eight manoeuvres rolled; the engine's side held on every
  one:
  - disarm, failed by 10: "Kesst Vayr drops the rapier." — the rapier left `weapons`, the
    hand was `unarmed`, the ledger held "Kesst Vayr's rapier" at the tavern, and the
    next swing resolved as an unarmed strike;
  - bull rush by 7: "driven against something solid and goes nowhere" — the square did
    not change (the push ran into the bar);
  - steal the purse, failed by 16 with the fastened +5 in the CMD: the 9 sp stayed his;
  - dirty trick, trip, overrun failed; the drag line was a grapple by the model's own
    choice ("grab" is a grapple cue, and nothing overruled it this time).
- **The prose did not hold to the tells on four of those turns**, the narrator's fault
  and not the engine's, and not caught by any detector: the player's backfired disarm
  was narrated as HIS grip failing ("He stumbles back, his balance ruined by the sudden
  loss of the steel"); the blocked bull rush left him "momentarily stunned"; the failed
  steal sent "the purse tumbling from his hip" to the floor; the unarmed swing was "your
  blade", and the failed overrun had "your rapier slips from your grip" — a rapier
  already on the floor two turns. Every one is prose asserting a mechanical outcome no
  tell carried; the claims scrubber (`intents.cut_outcome_claims`) does not look at
  items leaving hands, conditions, or who dropped what. Open.
- Not seen live: a SUCCESSFUL disarm, steal, trick, drag, reposition or overrun. The
  dice did not give one in eight rolls; those paths are covered by
  `tests/test_maneuver_outcomes.py` only. No model chose reposition for "I steer him
  into the corner" (a plain unarmed attack came back), and review never adds a
  manoeuvre the model left out.
