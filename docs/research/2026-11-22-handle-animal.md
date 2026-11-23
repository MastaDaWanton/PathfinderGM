# Handle Animal, wild empathy and words to animals (round 3, 2026-11-22)

The owner's ruling: "Companions can still obey in character but companions that are
animals/beasts are unable to communicate without the use of magic. So handle animal
functions almost as diplomacy in many ways." Built in `rules/animals.py`.

## Sources read

- d20pfsrd.com/skills/handle-animal (CRB text): handle DC 10 (move action), push DC 25
  (full-round), +2 when the animal is wounded or has nonlethal or ability damage; teach a
  trick in a week at the trick's DC, Int 1 learns three, Int 2 six; train for a purpose
  (combat riding DC 20 / 6 weeks, upgrade from riding in 3; fighting, guarding, heavy
  labor, hunting, performance, riding); rear DC 15 + HD in a year, never retried; half the
  time is spent before the check (3 hours a day per animal), a failure ends it; a creature
  of Int 1–2 that is not an animal at +5; untrained, a Charisma check handles and pushes
  domestic animals only; a druid or ranger handles her companion as a free action, pushes
  as a move action.
- d20pfsrd.com/classes/core-classes/druid: wild empathy "functions just like a Diplomacy
  check made to improve the attitude of a person", 1d20 + druid level + Cha, within 30
  feet, about a minute, a magical beast of Int 1–2 at −4; domestic animals start
  indifferent, wild ones unfriendly.
- d20pfsrd.com/classes/core-classes/druid/animal-companions: Link (free handle, move push,
  +4 circumstance on wild empathy and Handle Animal regarding the companion); bonus tricks
  need no training and do not count against the limit. The page says nothing about a
  companion of Int 3+ understanding speech.
- d20pfsrd.com/skills/diplomacy: "You cannot use Diplomacy against a creature that does not
  understand you or has an Intelligence of 3 or less."
- d20pfsrd.com/skills/ride: control a mount not trained for combat riding in battle, DC 20,
  a move action, failing it "you can do nothing else in that round"; no roll for one trained
  for combat; fight with a combat-trained mount DC 10, a free action.
- The bestiary's own records (content/bestiary/core.json): every animal prints `languages:
  []` (dog, horse, wolf, camel, cat, pony); the griffon prints "Common (cannot speak)", the
  worg "Common, Goblin". That is the test `animals.wordless` uses.

## Prior art

- Foundry VTT PF1: no module automating tricks or Handle Animal could be found; the closest
  (Koboldworks' companion link) shares roll data between actors. Could not confirm more.
- Owlcat's Kingmaker and Wrath control animal companions directly as party members, which
  the 2026-10-01 ruling refused. I could not confirm whether they model Handle Animal; a fan
  wiki says companions cannot be chosen for dialogue skill checks.
- No tradition was found that was tried and abandoned for this; said plainly.

## What was built

- Words: a `say` to a wordless beast tells "does not understand words" and opens no
  conversation (`Engine._op_say`, `join_talk`); a `greet` is refused; companions' orders
  (`gm/companions.orders_for`) and addressed answers skip it. `permission.speak_with_animals`
  (the spell's permission, now granted by the cast's buff door) lets words reach animals.
- Diplomacy at a creature that cannot understand or has an animal's mind: refused with the
  fix named, or — for a druid or ranger — wild empathy, through `attitude.influence_dc`,
  `Engine._sway_refusal` and `Engine._sway` (the same machinery).
- Handle Animal's uses as rows of content/rules/skill-uses.json; tricks are `trick.<name>`
  tags laid by ActiveEffects; a handled command is `handled.<trick>`; the animal's own
  fight turn is told the command and held to an attack it was handled to make
  (`companions.handled_unheeded`). Teaching, training and rearing wait In progress.
- Bought mounts carry their training (`stall-lines.json` `trained`); Ride's control in
  battle asks `animals.combat_trained`.
- The reader: no reader prompt text was added. Words to an animal are detected off the
  target's tags in the act table (`acts_to_ops._to_an_animal`), which declares a Handle
  Animal check; its trick, purpose and `at` are closed enums in the declared schema.

## Owner calls made (RAW where the book was silent, else stated)

1. A hostile animal takes no command (handle or push is refused; calm it first). The book is
   silent; "functions almost as diplomacy" was read as attitude mattering.
2. Rearing: the world has no young animals, so a wild animal that is at least indifferent and
   travels with you can be reared; a year domesticates it.
3. Bought animals: horses, ponies, the camel and the riding dog are trained for riding; mules
   and donkeys for heavy labor; the dealer's "(combat-trained)" line for combat riding. The
   riding dog's own training could not be confirmed (the CRB equipment page could not be
   fetched).
4. A mount that knows every combat riding trick (a companion's bonus tricks can) counts as
   combat-trained.
5. Wild empathy is refused in a fight (a minute's work by the book). Diplomacy is not
   refused in a fight today; that parity is left alone.
6. Out of a fight, a handled attack is made at once through the battle gate; in a fight it
   is the animal's next turn.
7. Int 3+ animals: the book names no trick limit here, so none is applied.
8. Mounts bought before this change carry no training (the old save recorded none), so they
   need the control check in a fight.

## Not built

- Teaching "obey only you" (exclusive) and "attack any creature" (two tricks).
- A combat-trained horse's hooves as primary attacks (Docile); the Ride "fight with a
  combat-trained mount" use.
- The Animal domain's speak with animals by rounds (its pool is counted, no op spends it).
- Commands other than attack are told to the animal's turn but not held to it.
