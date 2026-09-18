# Things and their owners

Group 2 of the fix pass after the 2026-09-18 play-test (`docs/playtest-2026-09-18.md`,
item 15 and item 22's payment). Branch `things-and-owners`, 2026-09-18. Tests:
`tests/test_things_and_owners.py` (10).

## What was wrong

A sundered club became "a chunk of wood" the player picked up, then "the smoldering
wood of the table still glowing faintly where his final strike landed" two beats later:
fire from nothing, a table from nothing. Nothing grounded THINGS the way the cast ledger
grounds people. Ownership existed only by containment — an `Item` inside an actor's gear
with hardness and hit points, nothing about whose it was or what it had been — and
nothing at all existed off a person: a dropped weapon, fragments, a chunk of wood on the
ground had no record. "I pay her ten gold" reached the engine as `sell gold_coins_10`
and was refused while the prose took the coin. "i pick up a chunk of wood and throw it
at the man" became a `give` and a `cast`. The goods held "scene on" ×3, read out of the
Continue directive. The narrator was shown neither the purse nor the goods, ever.

## Prior art, and what it settled

Searched before designing, as the standing instruction requires:

- **Creation Kit (Skyrim)**: every placed object reference carries an owner (an NPC or a
  faction, optionally a rank) beside the stolen flag — ownership is a fact about the
  object, not about who holds it. ([UESP: Creation Kit ownership](https://ck.uesp.net/wiki/ObjectReference_Script),
  [setting ownership](https://steamcommunity.com/app/72850/discussions/0/343786746007231270/))
- **Inform 7**: one containment tree; a dropped thing lands on the room's floor; a room
  may declare a drop zone; only what is carried can be dropped.
  ([Writing with Inform 3.25](https://ganelson.github.io/inform-website/book/WI_3_25.html),
  [Recipe Book 6.8](https://ganelson.github.io/inform-website/book/RB_6_8.html))
- **Dwarf Fortress**: items are claimed; the claim outlives the carrying, and clearing it
  is a separate act. ([DF wiki: Claim](https://dwarffortresswiki.org/index.php/DF2014:Claim))

So: one record per thing, with exactly one of `held_by` (a ref) or `at` (a place id),
and beside it `owner`, `from_` (provenance), `state`, `material`. Ownership does not
change because the thing changed hands.

## What was built

- **`Scene.props`**, saved and loaded. `place_prop` (dropped, thrown, left in pieces),
  `hold_prop` (picked up; owner and provenance kept), `prop_named`, `props_here`,
  `prop_on_the_ground(asked)` — by name, then by a shared word with what it is, what it
  was or what it is made of, so "a chunk of wood" is the fragments of a wooden club.
- **Sunder leaves fragments** at the spot: "fragments of the challenger's club", his,
  of wood; his hand empties. `_op_give` from the world picks THAT record up when one
  matches and says whose it is ("— the challenger's, not Kesst Vayr's"); a drop lays the
  thing here with its record. A thing nobody made real is still taken from the world.
- **The brief says what is had and what lies here**: the PC's line carries `HAS (fact):
  purse …; carrying …` with owner and provenance beside each thing; `scene_now` carries
  "lying on the ground here, and nothing else is: …".
- **An improvised weapon** is in the table per the Core Rulebook (-4 through the
  proficiency check, 1d4, thrown at 10-foot increments). `inject_improvised` reads
  "throw it at the man" / "hit him with the chair leg", names the thing on the attack
  (`item`, `thrown`), drops a `cast` the model dressed the throw as, picks the thing up
  first when it is not carried, and the engine lays a thrown thing where it fell.
- **Coin by amount**: `inject_payment` turns "I pay her ten gold" into a `give` of gp from
  the purse to the person paid, and a model `sell gold_coins_10` into the same give.
- **Words for what is happening are not goods**; the Continue directive buys nothing.
- **Fire from nowhere**: fire damaging a thing with no source in the place or the recent
  beats is a finding, cut as the backstop.

## Measured live, one replay on a copy of the `masta` save

Eight lines through `/api/say` and `/api/roll`: stand and stare down; wait for a
challenger; the insult; strike the weapon and sunder it; pick up a chunk of wood and
throw it at him; hand the woman ten gold coins; drop the chunk of wood; Continue.

| | Result |
|---|---|
| Payment | purse 231 → 221 gp; "Masta hands woman 10 × gp"; the beat: "The coins clink as they fall into her palm" |
| Throw | "Attack with chunk of wood" 1d20, "Damage (chunk of wood)" 1d4; hit for 20; "The chunk of wood lies where it fell"; award "for Ashla Ironvale" |
| Drop | "Masta sets down chunk of wood; it lies here"; ledger: `chunk of wood`, owner pc, at the market |
| Declaring turn | the prose landed the sunder; `swing-not-yet-struck` cut one sentence and the declaration stood — half the landing ("weapon's destruction … empty hands") was outside the vocabulary: widened |
| Target | the man who squared off was "the brute", not a cast role word, so he was never booked and the sunder went to a resident standing nearby: `brute`, `bruiser`, `ruffian`, `challenger`, `veteran` … are role words now |
| Continue | "Ashla Ironvale stabilises where they lie"; the wood "remains heavy on the dirt" — the ledger's record, held |

## Left open

- The pick-up the injector inserts first arrived after the attack in the resolved list
  (the attack does not need possession, and the end state was right); the ordering is
  worth a test on the plan chain.
- `contradicts-the-engine` read "woman is described as down" for a beat about a
  different woman, because an actor named "woman" matches the common noun — group 4.
- A model-introduced fire ("the crackle of the nearby fire") grounds later fire damage;
  the guard is about damage with no source, not about scenery.
