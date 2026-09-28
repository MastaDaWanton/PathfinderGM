# Two of a name, and a name cut short

*Design record, 2026-09-27. The code is `rules/bestiary.py` (`name_apart`, called from
`instantiate`), `gm/narration.py` (`cut_dead_men_walking`, `_shared_with_the_living`),
`gm/agent.py` (`_groom` builds the living list) and `gm/judgement.py`
(`_rest_of_the_description`, called from `note_cast`). The tests are
`tests/test_two_of_a_name.py` and `tests/test_a_description_is_whole.py`.*

Both defects turned up in the 2026-09-27 fight audits (`tools/narrator_audit.py --script
fight --turns 12`, gemma-4-12B; docs/wrong-actor.md, "Paired runs").

## Two actors called "thug"

The scene's names were `['Kesst Vayr', 'Borin Lyraxys', 'thug', 'thug']`. The spawn door
(`Engine._bring_in` → `bestiary.instantiate`) minted the second thug under exactly the
first one's name, and nothing checked. Once one of them died, every door that finds
people by name answered for both:

- `_groom`'s `cut_dead_men_walking` cut "The thug lets out a desperate, rattling groan and
  shuffles forward…" on the **living** thug's own turn. That was the one sentence saying
  who was acting, so a rewrite call had to put a thug back.
- The brief told the model "dead on the ground here: thug" and "hostile towards the
  player: thug" in the same breath.

### What the traditions do (looked up before designing)

- **Foundry VTT**, unlinked tokens: "Append Number" and "Prepend Adjective". One Kobold
  actor places "Angry Kobold (1)", "Eager Kobold (2)"
  ([foundryvtt#17](https://github.com/foundryvtt/foundryvtt/issues/17)). Its adjective
  list has had open complaints since
  ([#11200](https://github.com/foundryvtt/foundryvtt/issues/11200),
  [#14535](https://github.com/foundryvtt/foundryvtt/issues/14535)).
- **Inform 7** lets duplicates of a kind stay indistinguishable. When the player's words
  fit more than one thing, the parser asks "which do you mean?"
  ([Writing with Inform §4.14](https://ganelson.github.io/inform-website/book/WI_4_14.html)).
  Zarf's [survey of parser disambiguation](https://blog.zarfhome.com/2024/01/parser-if-disambiguation)
  argues this belongs at the disambiguation stage, not the matching stage.
- **Diku-family MUDs** target the second of a name as `2.guard`. I know this from play
  and could not confirm it against a primary source in this pass.

What we took, and what we refused:

- **Refused: Inform's question.** Our reader is a narrator writing prose, not a player
  typing a command, and there is nobody to ask.
- **Refused: Foundry's number.** It reads as a label on the page ("thug (2) groans").
- **Refused: Foundry's adjective.** It asserts something about a face the world rolled
  separately (`rules/faces.py`), which makes it an invented trait.
- **Taken: an ordinal.** It is neutral, it reads as English, and it is already this
  engine's own idiom: the boarding crew in `Engine._defenders` are "a hand", "a second
  hand", named apart for exactly this reason.

### Built

- **The mint** (`bestiary.name_apart`, inside `instantiate`, the one minter).
  - A newcomer whose name somebody here already wears gets the first free ordinal:
    "second thug", "third thug", "a second hand". The article is kept.
  - Somebody here dead counts too: a body still wears its name, and the dead thug is
    exactly who the living one was mistaken for.
  - A resident of the world (a `world_entity_id`) keeps their own name.
  - Only the newcomer is renamed. The first thug has been "the thug" on the page for
    turns, and renaming him would contradict every beat already written.
  - `troops.form`'s throwaway member pattern is instantiated without a scene, so a
    unit's members stay "Raider", never "second Raider".
- **The cut** (`cut_dead_men_walking(..., living=...)`). A dead name that the sentence
  used, and that fits a living actor's name word for word, is not evidence of a corpse
  acting, so the cut declines. The fit counts when the words sit anywhere inside the
  living name, because after the mint fix the model still writes "the thug" for the
  second thug. Names now match as whole words, longest first, so "second thug" is read
  before "thug" and "thug" no longer matches inside "thuggish".
  - **The cost, stated:** a dead "thug" who really does rise beside a living "second
    thug" is no longer cut.
  - **Also a change:** "thugs" (plural) no longer matches a dead "thug".

## "man with a thick"

`tests/replay/2026-09-25-fight-bodies-plain-gemma4-12b.jsonl.gz`: the setup beat wrote
"a man with a thick neck and a weary face leans against the bar", and the scene gained
**man with a thick**. Its tells read "man with a thick's attack misses Kesst Vayr".

- **The cut** is `note_cast`'s description tail. The slot there is one word after the
  article, plus an adjective it recognises. "thick" is neither on the word list nor
  adjective-shaped, so it took the noun's place and "neck" was left behind.
- **Still live after the prose stopped making bodies.** `note_cast` books the stump,
  `record_people` gives it a life, and `embody_sought` walks it on when the player turns
  to him. Worse, with the stump booked, "I talk to the man with the thick neck" found
  nobody at all: "neck" is not a word of "man with a thick".
- **This is the third fix of one shape.** "heavy" went onto a word list (2026-09-19),
  the adjective endings came next (2026-09-20, "distinctive"), and "thick" is on
  neither.

### Measured, and fixed from the other side

Over the 239 beats in `tests/replay/`, 13 tails ended one word short:

| Stump the tail booked | Word left behind | Times |
|---|---|---|
| with the thick | accent | 3 |
| with a thick | neck | 2 |
| with a missing front | tooth | 2 |
| in a stained leather | apron | 1 |
| in a stained leather | harness | 1 |
| in a stained leather | jerkin | 1 |
| with the wild | mane | 1 |
| with a wide | wingspan | 1 |
| in the silk | robes | 1 |
| with a sharp | intelligent face | 1 |

On top of those 13, 8 beats wrote our stump back as prose: "The man with a thick
grunts."

Chasing another word would repeat the last two fixes, so the fix reads the word that
follows the tail instead:

- Every word that followed a **whole** description in those beats was one of three
  kinds: a verb in -s ("watches", "lies", "steps"), a function word ("is", "and", "of"),
  or a preposition ("across").
- Every word that followed a **cut-short** description was a plain noun.
- So `_rest_of_the_description` takes one more word when it is none of those three
  kinds.
- A word in -s counts as a plural noun only when an auxiliary follows it: "the silk
  robes is now visible", never "the bread watches you".

After the fix:

- **12 of the 13** stumps book whole.
- **0 of the 20** whole descriptions followed by a verb or a function word gained a
  word.
- The 2026-09-18 live replay in `tests/test_fight_from_either_side.py` had pinned a
  stump of its own: "man in the scarred leather" is now "man in the scarred leather
  vest".

Not reached:

- **"a woman with a sharp, intelligent face"** (1 of the 13). A noun followed by a comma
  is also how a clause starts ("a man with a sword, who …"), so the comma stays with the
  older rule, which drops only a known adjective.
- **An irregular past tense after a whole description** ("a man with a club swung")
  would be taken as the noun. The recorded prose is present tense throughout and held
  no such case.

### Saves written before the fix

The replay corpus's saves hold "sturdy woman with a missing front". Read whole, "a sturdy
woman with a missing front tooth" no longer equals that ledger phrase, and it booked her a
second card on 2 of 142 replayed turns (note_cast booked 76 → 78). A player's save from
before this change would do the same.

`note_cast` now treats a ledger phrase with a description in it, which the new phrase
extends by exactly one word, as the same person. A bare "man" is not a stump of every man
described after him. With that in place the corpus counts are back to the baseline
(76 booked, 62 noted), and the only difference left is 7 bookings that are now whole.

## Live

`tools/narrator_audit.py --script fight --turns 12`, gemma-4-12B
(`igorls/gemma-4-12B-it-heretic-GGUF`), 2026-09-27, on this branch.

- **11 of 12 turns clean.** The one fault is `combat-turn-did-nothing`, which is not a
  naming fault.
- **Neither condition came up.**
  - The model spawned one creature, not twin thugs, so the mint had nobody to tell apart.
  - Nobody died, so the dead-men cut never ran; the run held no "dead stayed dead"
    repair at all.
  - The prose described nobody with a cut-short tail. The one described person was
    booked by the plan's `introduce`, not by the tail.
- **So the live run shows these changes break nothing on the fight path. It does not
  show them working.** That evidence is the replays:
  - The recorded setup beat that made **man with a thick** now books "man with a thick
    neck", and turning to him embodies that name. Before, turning to him found nobody.
  - The audit's scene, two "thug"s and one dead, driven through the real `_groom`: the
    living thug's groan survives. With the guard switched off, the same test reproduces
    the audit's failure exactly: "the dead stayed dead: cut 1 sentence(s)" and an empty
    beat.
- **Timings are not comparable** with docs/wrong-actor.md. Two other sessions were
  running the model at the same time, and three turns spent about 12 minutes each
  queued.
- **A third naming defect surfaced**, and it is not fixed here. The plan aimed an attack
  at "new1", the `introduce` placeholder, without declaring an introduce. The
  invented-ref repair (`judgement.py`, `re.sub(r"\d+$", "", invented[0])`) then spawned a
  thug called **new**. It is flagged as its own task, because whether a stray
  placeholder should spawn anybody at all is a declared-not-guessed question, not a
  naming one. Fixed on the branch placeholders-are-ours. See docs/declared-not-guessed.md,
  "a placeholder is ours".
