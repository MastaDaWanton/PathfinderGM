# A disarmed creature takes its weapon back up

*Design record, 2026-09-27. Branch `creature-recovers-weapon`, on `maneuver-outcomes-in-state`.
The code is `gm/judgement.py` (`rearm_step`, `rearm`, `rearm_note`, called from
`GMAgent.npc_turn` and `default_npc_action`), `rules/reactions.py` (`provoking_action`,
`provoked_by_action`, `disarmed_and_empty_handed`), `rules/engine.py`
(`Scene.within_reach`, the `square` on a props record, the ground branch of `_op_give`,
`_provoked_by_pick_up`, the resolution-time check in `_op_attack`, `_instrument`) and
`rules/weapons.py` (`described`). The tests are `tests/test_creature_rearms.py`.*

## The report

`docs/maneuver-outcomes.md` left this open: a disarm put the thug's sap on the ground, and
the legality check refused him swinging it there. Nothing let him recover it:

- On the model's path, the creature turn's op list (`_CREATURE_OPS`) has no `give`. The
  refusal told the model "Picking it up is a give", which it had no way to write.
- On the fallback path (`judgement.default_npc_action`, the only path with Ollama down),
  the creature swung `equipped`, which the disarm had set to "unarmed".

Measured on the code before this change, with the combat panel's End turn and the
fallback: six rounds, six swings, every one "Attack with unarmed strike". The sap lay in
the thug's own square and a dagger was on his weapons list the whole time.

## How others do it

Primary sources, checked by a second pass (the two central claims re-read at source):

- **Pathfinder 1e**, Table 7-2 (aonprd.com, Actions in Combat):
  - "Pick up an item" is a move action and provokes.
  - "Draw a weapon" is a move action and does not provoke; with BAB +1 it can be combined
    with a regular move (footnote 3).
  - "Attacking unarmed provokes"; "An unarmed character can't take attacks of opportunity."
- **Greater Disarm** (Normal line): "Disarmed weapons and gear land at the feet of the
  disarmed creature." The 3.5 SRD says "in the defender's square".
- **TemplePlus** (ToEE, `TemplePlus/ai.cpp`), the closest engine to this one:
  - `StrategyParse` begins `// check if disarmed, if so, try to pick up weapon`, before any
    strategy tactic.
  - `PickUpWeapon` returns early if either weapon slot is already filled or the weapon is
    not within reach. It never walks to it.
  - The action, "Retrieve Disarmed Weapon", is a move action flagged to trigger an attack
    of opportunity. Its changelog: "AI uses this too when disarmed so you can't
    completely cheese it!"
- **ROM 2.4** `fight.c:disarm()` puts the weapon on the floor, and an NPC that can see it
  takes it at once (`get_obj`, no wait state) — and never re-wields it.
  - **Merc 2.2** and **SMAUG** put an NPC's weapon straight into its inventory.
  - Free and instant is the MUD answer. 1e prices it.
- **NetHack** re-wields from inventory first ("This may cost the monster an attack").
  - Its bullwhip snatch had a branch where the snatched weapon hit you, now under `#if 0`:
    tried and abandoned.
- **Baldur's Gate 3**, Early Access Patch 5: "Disarmed characters now look for replacement
  weapons", and archers were given backup melee weapons.
- **Tried and abandoned elsewhere:**
  - PF2e made a disarm drop the weapon only on a critical success.
  - Paizo raised the weapon cord's re-grip from a swift action to a move action (Ultimate
    Equipment FAQ).
  - Both moves say recovering a weapon was too cheap.

## The rulings

The user's (2026-09-27), asked as design choices:

1. **The engine decides, first.** This is TemplePlus's shape. `judgement.rearm` runs on both
   creature paths, so it holds with the model down, and the model is not trusted to choose
   it.
2. **Pick it up, else draw, else fists.**
   - The weapon it chose to fight with is recovered if it is in reach.
   - Otherwise it draws a weapon it still carries, which provokes nothing.
   - It uses its fists only when it has neither.

The rules parts were not choices:

- **It costs a move action.** What is left is one swing: no full attack, no second attack.
  - A move of more than a five-foot step goes too when the foe is in reach.
  - When the foe is not in reach, the swing goes and the move stays: pick up, then close.
  - A plan with no swing keeps its move, because two move actions are legal.
  - A draw at BAB +1 or better rides along with a move.
- **Only within reach, never walking to it.**
  - The props record now keeps the `square` the weapon fell in (its owner's).
  - `Scene.within_reach` measures the natural reach from the edge of the creature's space.
    A glaive strikes 10 ft off and cannot pick a sap up there.
- **Picking up provokes, for everyone.**
  - `_reactions_before` routes a ground `give` to `provoked_by_action`, which uses the same
    `threatens` a move asks.
  - The player's own pick-up now provokes too: one rule.
  - A pick-up out of reach is refused with the fix named ("Move next to it first").
- **A disarmed creature with nothing in hand does not threaten** (`disarmed_and_empty_handed`).
  This is the book's unarmed rule, applied only where it is safe: a creature whose own
  weapon the ledger holds elsewhere.
  - The general rule stays refused, for the reason `_reach_of` gives: every bestiary
    creature would stop threatening.
  - Without this, the pick-up provoking gave the thug a punch at the player stooping for
    his sap.
- **A blow that drops the creature as it stoops ends the pick-up and the swing.**
  - The give applies the move's rule ("never picks up the sap").
  - So does a fresh attack at resolution ("never swings"). Measured: the attack of
    opportunity put the thug unconscious, and the swing queued behind the pick-up still
    rolled.

Refused: adding `give` to the creature's op list. With no giver and no record, a give
comes "from the world, which never runs out", so a creature could mint a greatsword
mid-fight.

## How it reads

- The pick-up: "the thug takes the sap back up off the ground; it is in hand again."
  - It was "the thug takes sap.", which said neither that it lay there nor that it is held.
- The draw: the existing `wear` tell, "the thug draws the dagger."
- The attack of opportunity's reason: "the thug stooped for the sap within reach".
- **Every weapon swing now names its weapon in the tell**, as the instrument after the
  defender (`_instrument`): "the thug hits Kesst Vayr with the sap for 4 bludgeoning."
  - Measured live: the thug swung his sap three rounds running and the prose had him
    grabbing a forearm, punching ribs and raking with "its taloned limbs". Nothing the
    narrator was fed said what was in his hand, and the brief describes a Korvu's talons.
  - The weapon is never the subject: a tell that opened with an object once had the model
    hand the blow to the player (`narration.wrong_hands`).
- **The creature turn's prompt states what is in hand, and what that is**, in the weapon
  row's own words (`weapons.described`): "In hand: the sap (a light one-handed bludgeoning
  weapon: weighted head, wrapped grip)."
  - Told only "the sap", the local model wrote "a heavy vial of sap" whose "sticky liquid
    splashes wide".
  - Every weapon named with an ordinary word is the same trap.

## Measured live

Four scripted runs through the HTTP loop (`/api/combat/act` End turn, `/api/say`,
`/api/roll`), gemma-4 12B heretic. The thug was disarmed in setup with an aimed CMB die and
stood adjacent to the player.

Five creature turns per run: two in the first step (the turn the roll interrupted, then
the next), then one per step.

| run | what the narrator was given | re-armed on turn 1 | wind-ups naming the sap | beats with the sap as a liquid |
|---|---|---|---|---|
| 1 | rearm only | yes | 1 of 5 (turn 1, from `rearm_note`) | 0 |
| 2 | + the weapon in the tell | yes | 1 of 5 | 0 |
| 3 | + "In hand: the sap" | yes | 5 of 5 | 6 |
| 4 | + the row's gloss | yes | 5 of 5 | 0 |
| 5 | the same, repeated | yes | 5 of 5 | 0 |

- **Grabbing, fists and talons.** In run 1 the outcome beats after turn 1 had the thug
  seizing a throat, clamping a forearm, driving his fist and raking with talons.
- **Run 2, once the tell named the weapon.** The outcome beats said "weighted leather
  whip", "heavy leather club" and "the heavy sap strikes your chest" (beside a stray "fist
  connects"). The one tell still without a weapon, the natural 1, got "arms flailing". It
  names the weapon now.
- **Runs 4 and 5.** Every beat, wind-up and outcome alike, has the sap as a blunt
  weapon.
- **Timings are not a measurement.** The runs shared the one Ollama with other sessions.

## Still open

- **The narration after a reaction roll inside a creature's turn.** The player's attack of
  opportunity suspends the thug's turn, and `/api/roll` resumes it through the player-turn
  narrator. With no player sentence to anchor it, a worked example reached the page
  verbatim ("You break contact and the window is four running steps away"). A
  move-provoked attack of opportunity reaches the same path, so this predates the change.
  Spun off as its own task.
- **No per-turn action economy.** Move + full attack is legal everywhere else today. The
  trimming here covers only the re-arming turn. The enemy-tactics plan's phase 0 is the
  general fix.
- **Melee and manoeuvres have no reach check.** The fight in the first probe laid the two
  10 ft apart, and the disarm and the thug's swings resolved at that range. Branch
  `maneuver-reach` is on it. The re-arm's own reach questions are measured.
- **Only the pick-up provokes of the Table 7-2 "yes" rows.** Retrieving a stored item,
  casting, an unarmed attack against an armed foe, and a manoeuvre without its Improved
  feat (`MANEUVERS[...]["provokes"]` is read by nothing) all still provoke nothing.
- **A thrown weapon's record has no square** (`place_prop` is not told where it landed), so
  a reach question about it is unmeasurable and answered "in reach".
- **Greater Disarm's 15 ft** is not modelled. A weapon always lands in its owner's square.
