# Turn resolution: playtest 2026-11-23 items 3, 4, 11, 12, 18

Lane fix/turn-resolution, 2026-11-25. Sources were read on the day. Where a claim could not be
sourced, the note says so.

## Sources

- d20pfsrd, Combat (mirrors the CRB's Combat chapter):
  https://www.d20pfsrd.com/gamemastering/combat/
  - "When combat begins, all combatants roll initiative." "Combatants act in initiative
    order (highest to lowest)."
  - Surprise: "If some but not all of the combatants are aware of their opponents, a
    surprise round happens before regular rounds begin."
  - "In a normal round, you can perform a standard action and a move action, or you can
    perform a full-round action."
  - Coup de grace (Helpless Defenders): "You automatically hit and score a critical hit",
    then a Fortitude save or die. It is a full-round action that provokes.
  - Withdraw: "Withdrawing from melee combat is a full-round action."
- Foundry VTT, Combat Encounters: https://foundryvtt.com/article/combat/. The GM builds an
  encounter, rolls initiative (Roll All or Roll NPCs, or players roll their own), and presses
  **Begin Combat**, which "begins tracking round number and turns". Entering combat is its own
  act, separate from any attack.
- Baldur's Gate 3, Turn-based mode: https://bg3.wiki/wiki/Turn-based_mode. The player can
  toggle turn-based mode outside combat, and it is used to position for surprise attacks.
  Fan wiki only; it flags part of the entry as unverified. Guides agree on Shift+Space. PC
  Gamer says the mode is for "positioning for surprise attacks".
- Owlcat, Pathfinder: Wrath of the Righteous turn-based mode: switched with T, real-time and
  turn-based both available
  (https://progameguides.com/pathfinder-wrath-of-the-righteous/how-to-switch-to-turn-based-mode-in-pathfinder-wrath-of-the-righteous/).
  I could not find an official Owlcat statement of a "start combat now" command. Players on
  Steam start fights on their own terms by sending a tank to charge. Unconfirmed in a primary
  source.
- MUD practice: in Diku-style command tables, flee needs the "fighting" position, and the
  guides say plainly that once you start a fight you cannot just walk away from it. You FLEE
  or are RESCUED (https://www.gammon.com.au/forum/?id=6768). MUME: after attacking, "you
  can't flee the fight for a full flee round" (https://docs.mume.org/wiki/pages/Flee). I did
  not find the exact Diku source string.

## #3: "I attack the scholar" with a place chip attached

**What happened.** Transcript #224 carried
`attachments: [{kind: place, id: …the-cold-hall}]`. The chip is attached by the exits row
(`11-exits.js` → `10-spells.js` `attachPlace`). It stays until a turn is taken
(`clearAttachments`), so it was put on after #223. `judgement.travel_to_the_attached`
appends the chip's travel last. The engine then ran `attack` (battle joined) and `travel`
("The fight is left behind. Left behind: the lost scholar").

**Rule.** Declaring the blow starts combat: initiative, then turns. Leaving is a move or a
withdraw on your own turn in the order. MUDs agree that once you start a fight, walking off is
a flee, never a free walk taken in the same command.

**Chosen.** The words win and the chip's walk is refused. The refusal is said ("Battle is
joined here: the way on to the cold hall waits until the fight is done"). It applies to
`travel`, `journey` and `venture` in any batch that joined a fight
(`Engine._held_by_the_fight_just_joined`). It sits at the engine so every door obeys it:
chip, plan and companion.

**Rejected.**
- Letting the chip win, so the attack is dropped: the typed words are the deliberate act.
- Clearing a chip whenever the words "look violent": that is a regex reading English (owner
  direction 2026-10-03).
- A UI warning: it would not stop the plan's own travel.

**Critic pass.** The critic objected that PF1e lets an attacker attack and then take a move
in the same turn. That is true, and the move is still allowed at the bar. But `travel` is not
a move action. It is a scene change between rooms ("a minute or two's walk"), always more than
one move, and it ends the encounter (`Scene.end_encounter`). That is a withdraw or a run done
outside the order, so refusing it in the batch that joined the fight is the book, not stricter
than it. The MUD flee lock is cited as tradition, not as PF rule.

## #4: "I finish the ramidreju" → narrate_only

**Reproduced.** The live reader (gemma-4-12B, scratch data) read "i finish the ramidreju" as
`consume, object: the ramidreju`, which is finishing as one finishes a drink. "I finish off
the ramidreju" was read `attack, blow: finishing`. The only demonstration of the killing
stroke said "finish off".

**Rule.** Coup de grâce, as above. Out of a fight the table already makes a blow at a downed
body the coup de grâce (`acts_to_ops.victims`), so the gap was the reading alone.

**Chosen.** The demonstration's own words changed to the bare verb ("I finish the jackal and
go through its pack."), at no cost to the prompt budget. The reader is 9 characters under its
measured ceiling, so a new demonstration would have needed a cut elsewhere. Live after the
change:
- "i finish the ramidreju", "I finish the clockwork spy", "i finish the wolf" and "I finish
  the dying thug with my dagger" → `attack, blow: finishing`
- "I finish my ale" and "I finish the stew and pay" → still `consume`.

**Critic pass.** The critic said a clockwork construct is immune to criticals, so it cannot
take a coup de grâce. That was the 3.5 rule. PF1e constructs and undead are not immune to
critical hits; the engine's `coup_de_grace.crit_immunity` (ooze, elemental, swarm,
incorporeal, or a printed immunity) already holds this, and refuses where 1e refuses. The
reader only declares; the engine decides.

**Rejected.** A keyword list for "finish". An engine rule turning a `consume` of a creature
into a blow: it is plausible as validation but no other case needs it, and it would rewrite a
reading.

## #11: "already down; Shadow holds the blow" on the downing blow

**Found.** The tell comes from the swing loop's guard (`rules/engine.py`, `_op_attack`). The
guard stops a queued swing after the defender is down. It fired on the Swift Strikes second
swing after the FIRST swing had broken the spy. It said "already down … holds the blow", and
then the state line ("is broken") followed. The narrator copied the contradiction (#211).

**Prior art.** MUD combat messages name the death on the killing round, and the next round's
swing does not exist. Diku's "pity" messages are for attacking corpses. I could not cite a
primary source for this.

**Chosen.** The attack's state records `down_at_start`. The held clause is said only of a body
that was down BEFORE the attack, which is its original case (pinned by
`test_a_swing_queued_behind_the_one_that_dropped_them_is_still_held`). On the downing blow the
fall is told by `_hp_state_tell`, and the swing that never came is not told.

## #12: an opening attack never lands

**Established from code and save.**
- The PC did not lose initiative. The initiator holds the turn (`_ensure_encounter`;
  re-probed over 6 seeds, 6 of 6 left the turn on the PC).
- The declared blow was held because the target was out of reach: the spy at 40 ft, the
  poltergeist at 35 ft. `_their_first_blow` had `if a.is_pc and closing is not None: return`,
  meaning "the player is never walked anywhere they did not say" (2026-10-01).
- The same blow typed a round later walks and strikes, under the owner's ruling of
  2026-09-29: "close the distance and strike if one move reaches" (`_closing_step`).
- The spy acting before the player came after a `/api/combat/act` 400 and then a 200 with no
  outcome logged, which is most likely a pass. This is inferred from the access log order.
  The engine record has no outcome for it.

**Owner's note.** "Being able to enter combat yourself to plan the strike". Foundry's Begin
Combat, BG3's turn-based toggle and Owlcat's turn-based mode all give the player a way into
combat that is not an attack.

**Chosen.**
1. **Start a fight.** It is a button in the book head's Here line, under the person pressed.
   It posts `/api/combat/act` with one `attack` carrying `squares_off`.
   - The engine forms the fight through the swing's own door: sides, rally, the law and the
     surprise round.
   - It rolls nothing and points the order at its top by initiative. No action was declared,
     so none is kept.
   - The NPC loop runs when a foe holds the first turn.
   - It is refused in a fight and at a body that cannot fight back.
2. **The typed opening blow is unchanged.** Out of reach, it still only joins battle. I tried
   closing it under the 2026-09-29 ruling: the PC exclusion was removed, and "I punch" at
   15 ft walked and asked for the d20. The full suite then failed 13 tests that pin the
   opposite on purpose:
   - `test_g2_close_and_strike.py::test_the_swing_that_opens_a_fight_still_only_joins_battle`
   - `test_gate_turn_order.py` ("out of reach, the opening blow waits for the panel", 8
     cases)
   - the law and rally tells in `test_encounter_coverage.py` and `test_arrest.py`

   That design (2026-10-01: "the player is never walked anywhere they did not say") was
   deliberate, and the owner's note points at the entry door instead, so I reverted it. It
   is listed as an owner call.
3. **Surprise round, for everybody.** A creature's opening closing walk is skipped while it
   holds `turn.one-action`. In the surprise round, the blow behind the walk would only have
   been refused afterwards.

**Rejected.**
- Auto-pathing any distance (BG3 and Owlcat do this in real time): the ruling caps it at one
  move.
- Making Start a fight keep the initiator's turn: that is a house rule for a declared action,
  and nothing is declared here.
- A new `begin_encounter` door from the table: `_op_begin_encounter` takes sides from the
  caller and skips the bystander, rally and law handling the swing's door does.

**Critic pass.**
- The surprise round allows one standard OR move action. The opening blow's closing walk is
  now skipped when the attacker holds `turn.one-action` (point 3 above).
- On "rolls nothing": Start a fight rolls initiative, hidden, as every fight's start does
  (`_ensure_encounter`), and Perception and Stealth for awareness. It rolls no attack and no
  damage.
- Two entry paths keep two turn orders, as the critic noted. The typed blow keeps the
  initiator's turn; Start a fight takes the book's order. This is an owner call.
- Two of the cited claims are not on the cited pages: BG3's Shift+Space comes from guides,
  not bg3.wiki, and Gammon's command table is SMAUG's, a Diku descendant.

**Owner calls (provisional).**
- Should a typed opening blow that one move reaches walk and strike, as the same words do a
  round later? I left it as it was: a deliberate 2026-10-01 design, pinned by 13 tests.
- Start a fight uses book initiative order rather than the initiator's turn.

## #18: "landing a blow piercing damage"

**Found.**
- The engine's tell said "for 15 bludgeoning and piercing".
- `narration.turn_numbers` read a number's words two deep ("bludgeoning and").
- `strip_turn_numbers` therefore lifted "for 15 bludgeoning and" out of the model's "landing a
  blow for 15 bludgeoning and piercing damage" and left "piercing damage".
- `page_line`'s amount pattern also stopped at two words, so the blow-shown repair handed the
  model the number to copy.

**Chosen.**
- A type pair is read with its "and".
- The "and" is kept out of the units and joined back only between two units, so a sentence's
  own "and" after the amount stays.
- `page_line` reads three words.

The root was the outcome reader, not the narrator's slot.
