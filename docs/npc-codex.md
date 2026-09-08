# The NPC codex

`rules/npcs.py`, the `npcs` kind in `rules/registry.py`, the NPCs bench in
`play/homebrew.py`, `tests/test_npcs.py`. Asked for by docs/quest-schemes-plan.md §6.3
(phase 3 of §6.10). Measured 2026-09-08 on the shipped bestiary.

## What it is for

A quest scheme names its people by role — "a trader", "a guard officer", "someone of
standing" — and never by name. The world's own cast supplies the person: their name,
their world entity id, where they live. This module supplies the **numbers**: which of
the bestiary's stat blocks that person plays as when the engine has to roll for them.

Before this, `_role_for` in `rules/schemes.py` gave every role the hand-written
guildhand, or the watchman if the role said "guard officer". Two blocks for every role
in every world, with 7,136 blocks already loaded.

## What the chooser does

`npcs.choose(role_words, level, prefer_named=False)` returns one block — its `id`, its
`name`, a display `role`, its `source`, the `cr`, the ladder it came from — or the
townsfolk floor. It is a sort over an index, and nothing else: no model is asked, no
number is authored, and the same words at the same level answer the same block every
time (`test_the_same_words_and_level_choose_the_same_block`). The index rebuilds when
the bestiary's own cache does, so a homebrew creature joins it without a restart.

**The index** (`npcs.index()`) is every block typed `humanoid` of small or medium size
with a challenge rating — people, not gargoyles, not fire giants. Of the 7,136 blocks,
3,747 are humanoid and 3,518 of those are person-sized. Tiered duplicates collapse:
Pathfinder Society writes one block per subtier (`captain-calgredine`,
`captain-calgredine-tier-3-4`, `captain-calgredine-tier-6-7`; 207 such ids, four spelt
`-teir-`) and the NPC Codex writes the iconics at three levels (`amiri-level-1`, 93 such
ids). They are one person with a level ladder, and the rung nearest the requested level
is what is used. Collapsed, the index holds **3,063 people over 3,515 rungs**, 338 of
them with more than one rung.

**The sort**, in order:

1. **Source rank.** The most generic source that has anyone matching a word wins.
2. **Words matched**, weighted by their order — the caller's first word counts most and
   matching two words beats matching one. `_ROLE_WORDS` in `rules/schemes.py` is
   written in that order: "someone of standing" is a noble before a sail master.
3. **Within one CR** of the target before further out; then the nearest rung.
4. **Fewest words that were not asked for**: "Guard" over "Caravan Guard" over "First
   Guard of Absalom".
5. The id, so ties are stable.

The target CR is `level - 1` (a character of class level L is CR L-1, Bestiary
"Creating NPCs"), floored at 1/2. A match more than **three CR** from the target is not
"near the level" and is dropped: measured before the cap, a 1st-level party's "someone
of standing" was the CR 6 Village Elder and their guard officer the CR 6 Watch Captain —
the right words and a fight nobody at the table could have. The Core Rulebook's
encounter table calls APL+3 epic; past it the floor is nearer than any block.

**The floor.** Nothing matching, or nothing near enough, gets one of the three
hand-written townsfolk in `bestiary.TEMPLATES`: the watchman for guard-shaped words,
the thug for thug-shaped ones, the guildhand for everyone else. The display role is
then the words that were asked, so the fill reads as what the scheme wanted.

## The source ranking, and why

| rank | sources | what they are |
|---|---|---|
| 0 | NPC Codex, Inner Sea NPC Codex, Game Mastery Guide | galleries of people by job and level; the names *are* role descriptions ("Border Guard", "Guard Officer", "Sea Captain") and the numbers were built to be anybody's |
| 1 | Villain Codex, Monster Codex, Inner Sea Monster Codex, NPC Guide | organised villains and the monstrous peoples' own specialists; generic, but shaped for the fight their author expected |
| 2 | everything else: `AP 100`, `PFS S3-Special`, `Rappan Athuk-…`, `Sword of Air-…`, `Curse of the Crimson Throne`… | a specific person from a specific story |
| 3 | the core Bestiary | almost no people in it; the few are a species' plain block |

Counted: 427 people at rank 0, 400 at rank 1, 2,193 at rank 2, 43 at rank 3. The
galleries come first because the plan asked for "generic people by class and level" and
that is exactly what they are; a story block is reached only when no gallery has the
word, or when the caller says `prefer_named=True` (a slot may say `"named": true`) for
a rival who should not be "Guard".

Measured on the words that made the ranking a question: both "guard" and "captain"
appear in Rappan Athuk's `trillok-captain-of-the-guard` and in nothing the NPC Codex
prints. Sorted by words matched alone, a 5th-level party's guard captain was a named
dungeon lieutenant at CR 7. With source first it is the NPC Codex Border Guard at CR 3.

## What the adventure-path blocks are, and are not, used for

An adventure-path or Society block is numbers. Its name is a person and a job — "Jevana
Drow Noble Priestess", "Captain Gortus Svard", "Trillok Captain of the Guard" — and only
the job is wanted. A proper name is found mechanically: a token that fewer than three
people in the index share. Measured over the 7,136 ids, 5,877 of the 6,778 distinct
tokens fall under that line and every one sampled was a name ("jevana" 2, "trillok" 1,
"vorg" 1, "gortus" 1, "absalom" 2), while every job word cleared it ("captain" 62,
"guard" 105, "priest" 50, "noble" 11, "drow" 17). So `jevana-drow-noble-priestess` is
offered as a **drow noble priestess** and `captain-gortus-svard` as a **captain**;
`abra-lopati` strips to nothing and is nobody's role. Joining words left dangling by the
strip ("vicar of the indomitable sea" → "of the sea") are trimmed off the ends.

The strip is applied to ranks 2 and 3 only. A gallery name is all description, and
"shopkeeper" appears in exactly one id — stripping it would lose the one Game Mastery
Guide shopkeeper for the very word that finds it.

**Never story.** The block's name, its languages, its spell list's flavour, its source's
setting — none of it reaches the cast member, the card or the narrator. The person on
the board keeps the cast's own name and `world_entity_id`; a role filled with nobody in
particular is named by the role asked ("guard officer"), not by the block, because a
Game Mastery Guide "Guard" is a fine name in any world and an Inner Sea "Thrune Agent"
is not. The tell about them is whatever the scheme says; the numbers are just numbers.

## The store

`homebrew/npcs/<world_entity_id>.json`, in the registry's own shape:

```json
{"id": "05b7a28595a3", "name": "Ariniel Thorne", "description": "",
 "creature": "border-guard", "world_entity_id": "05b7a28595a3", "role": "border guard"}
```

`npcs.remember` writes it the first time a scheme puts that person on the board;
`npcs.recall` reads it every time after, so the same person has the same numbers next
week. `npcs.block_for` is the one call `_role_for` makes: recall if the block still
exists, else choose and remember. A file that will not parse, or that names a creature
that no longer exists, is treated as absent — a bad edit on the bench must not stop a
scheme opening.

The **NPCs bench** (`/homebrew/`, `npcs`) is `ready` now. Its shipped count is the
3,063 people in the index; its rows are the codex's entries, each saying which block,
as what, for which world entity, and whether the block still exists. Opening a row is the
registry's generated form; correcting `creature` there is how a table overrules the
chooser.

## Still open

- **Relationship words are not jobs.** The kin slot's words ("sibling", "sister",
  "son"…) match nothing that means a relative; "sister-of-eiseth" and "kin-seeker" are
  what the bestiary has. The kin words now end in "farmer", "villager", "commoner" so a
  low-level kin is a Game Mastery Guide farmer, but at 5th level and up the Kin Seeker
  (CR 6) comes back. A proper fix is a separate *occupation* for the slot, chosen from
  the cast member's own facts in the export — the plan's "the character's facts" half of
  §6.3, which nothing reads yet.
- **Setting nouns in gallery names.** The Inner Sea NPC Codex is rank 0 and its names
  carry Golarion ("First Guard of Absalom", "Thrune Agent", "Razmiran Priest"); the
  rare-token strip does not run on rank 0. The display role only reaches the codex file
  and the bench, never the board, so it leaks nowhere a player reads — but a stoplist of
  setting nouns, or ranking that book below the NPC Codex, would be cleaner.
- **Word matching is prefix and plural only.** "priest" finds "priestess" and "guard"
  finds "guardsman"; "smith" does not find "blacksmith" and "merchant" does not find
  "trader". The `_ROLE_WORDS` lists carry the synonyms by hand.
- **The bench lists but does not yet offer a picker** for `creature`; it is a text field
  holding a creature id. The creatures bench's search is the obvious source for one.
- **No use outside schemes yet.** The GM's `bring_in` still names templates by hand, and
  the opening scene's people are still the hand-written townsfolk. Both could ask the
  chooser.
