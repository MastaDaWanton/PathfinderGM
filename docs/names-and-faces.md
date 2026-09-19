# People have names and faces

Group 3 of the fix pass after the 2026-09-18 play-test (`docs/playtest-2026-09-18.md`,
items 12, 21, 13c). Branch `names-and-faces`, 2026-09-18. Tests:
`tests/test_names_and_faces.py` (11).

## What was wrong

Asked his name, an NPC said "let's call it the stranger" — our placeholder — because
nothing on an actor held a real name behind the descriptor, no op renamed an actor, and
when the model DID give a name ("Kaelen") the un-namer struck it inside his own line:
`invented-name: names 'Kaelen'` → `people from nowhere: un-named Kaelen`. The woman in
the doorway was never described: the body checks stop the WRONG body and nothing
required A body; the brief carried no appearance for anyone, though every world
resident has an Appearance fact and every people a body in sentences. The homebrew
asura's body line rendered EMPTY (59 evolutions, `effects: []`), so with a nameless-race
brawler at 70 hp in front of it the NPC turn wrote "the beast".

The material was there and unused: the export's `play.names` — 80 pools of given and
family names, 16 keyed to PEOPLE entities — and `play.races`, each people's body as
sentences. No module read either.

## What was built

- **`rules/names.py`**: `people_of` (a settlement's people, read off its residents' own
  Identity sentences — the export does not say who lives where, the residents do),
  `pool_for`, `true_name` (given + family from the right pool, seeded off the ref and the
  place so a replayed save hands out the same name; never one already worn here),
  `appearance_for` (the people's body sentences, one or two, in the people's name),
  `resident_appearance` (a resident's own Appearance fact).
- **`Actor.true_name` / `Actor.appearance`**, saved and loaded, set at promotion
  (`promote_cast`, with the world) and at spawn (`Engine._bring_in`); the people a save
  holds from before the fields existed are named once on the next turn
  (`name_the_nameless`). The panel shows the descriptor until the name is given.
- **The brief** says, per person: "If asked their name they give it: X — until they give
  it, call them 'the stranger', never by that name" and "Looks (fact, use it when they
  are first described): …". Race and true names join the known names, so a given name
  survives the un-namer.
- **A name given in play** (`narration.introductions`: "call me X", "my name is X", or,
  when the player asked, a bare quoted answer — '"Gorvothor Kragnir," he grunts') is
  settled to the world's own name before the un-namer runs (`settle_introductions`) and
  renames the actor and the ledger (`judgement.apply_introductions`: whose name it is,
  in order of certainty — the person the world holds THIS name for, the speaker's head
  word, the player's addressee, the only unnamed person here). Refusing to give a name
  stays legitimate.
- **A face on arrival and on inspection**: a newly booked person whose sentences carry
  no appearance word (`faceless`) gets the world's body line appended as fact; so does
  the person the player looks over (`examined`).
- **Never a beast**: `creature_nouns_for_pc` turns "the beast / the creature" in
  narration into the player's name when everyone else here is a person; speech is
  untouched. `races.body_line` renders an unconverted homebrew card by type, size and
  evolutions; the PC line names the race when the heritage is blank.
- **Item 11 (from group 4, done here)**: the un-namer looks at the article already in
  front — "the Reeve's men" → "the men", "at the Reeve" → "at the stranger", never "the
  the".

## Measured live, two replays on a copy of the `masta` save

Five lines: stand and ask the stranger his name; look the woman in the doorway over;
the insult; hit him; Continue.

| | Replay 1 | Replay 2 |
|---|---|---|
| The name given | "Gorvothor Kragnir" — the world's Orc pool, tusks and all | "Gorvothor Kragnir", after a self-description ("broad-shouldered … weathered") |
| Panel renamed | **no** — a bare quoted name was not an introduction phrase | **no** — six descriptor-named people here and no role word in the sentence → the true-name match was added |
| Names in narration before given | **"Soren's eyes narrow"** for a woman nobody asked → the brief now forbids it | — |
| The woman looked over | posture and stillness, no face → `examined` added | described in the beat: "scarred lines of her jaw … thick muscles of her arms" |
| Old actors from the save | no names (c11, c16) → `name_the_nameless` added | c16 "Kael Throk", c17 "Gorvothor Korvath", c18 "Kael Throkos" |
| The player as a creature | "the Asura before him" (a race name, allowed) | — |

## Left open

- Every promoted person in Vormoor gets the same Orc body line; `appearance_for` varies
  the second sentence only. A dress cue from the settlement would separate them.
- On Continue the model wrote the NPC's own swing into the player's plan (a second swing
  that round). Item 23, group 4.
- "the Asura" for the player in an NPC beat is a race name, not a creature noun; whether
  the player wants their race used as a name is a table setting.
