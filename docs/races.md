# Races as documents

Built 2026-09-06 from "instead of picking the fantasy races that ship with pathfinder we
should be able to play as the races that ship with the world", with the standing rule
that it all follows the GAS-like framework (`docs/states-effects-tells.md`).

## What was there

Seven dicts in `rules/creation.py`, read by the forge; a sheet that asked
`race == "human"` for the extra rank, a forge that asked `f.race === "human"` for the
extra rank and the bonus feat, feat prerequisites that compared the race string. Elf's
"+2 Perception" was a line of prose the forge showed and nothing applied. A world's
peoples could not be played at all — the Korvu of the fixture world have wings, talons
and echolocation in their own entry, and the forge offered a halfling.

## What the traditions do, and what one abandoned

- **Paizo's Race Builder** (Advanced Race Guide) is the canonical vocabulary: a race is
  six *qualities* (type, size, speed, ability-score option, languages) and *traits* from
  nine categories, every line priced in race points, with a standard race capped at 10
  RP, advanced at 20, monstrous above. That is the price list `rules/races.py:rp` reads
  and the ceiling the house rule `race_rp` sets.
- **Foundry VTT's PF1 system** first held the race as a text field on the actor with the
  bonuses in code, and replaced it with a race *Item* carrying typed `changes` so a bonus
  travels with its source and leaves with it. That replacement is this design.
- **Foundry's PF2 system** keeps an ancestry as data — hit points, size, speed, boosts and
  flaws the player places, vision, traits, languages — and asks the player to place the
  boosts at build time. Our `choose` entries are those boosts.
- **5etools' race JSON** is data first (size, speed, darkvision as a number, trait tags)
  with the prose beside it, which is the shape `content/races/core.json` takes.
- **Nobody derives a race from prose at play time.** A world's people is turned into a
  document once, mechanically, and the document is what plays.

## The document

`content/races/*.json` ships the Core seven; `homebrew/races/*.json` holds the table's
own and the world imports; both read through `rules/races.py:all_races` with yours over
shipped, field by field. The grammar is the feat / class-ability grammar:

| Field | Meaning |
|---|---|
| `type`, `size`, `speed` | the Race Builder's qualities; the sheet's `size` and `speed` are set from them at creation |
| `mods` | fixed ability adjustments (`{"con": 2, "cha": -2}`) |
| `choose[]` | adjustments the player places: `{"amount": 2, "from": "any"}` (a human), or standard `+2 physical, +2 mental, -2 any` |
| `modifiers[]` | the feat vocabulary — `skill_mod perception +2 racial`, `combat_mod cmd +4 racial when maneuver=bull rush|trip` — read live by `Actor._race_mods` on every roll |
| `tags[]` | `race.<id>` always; `sense.darkvision.60`, `sense.low-light`, `immune.sleep.magic`, `move.fly.30`, `natural.claws`, `ferocity` — asked through `has_state`, priced from the table |
| `budget` | `{"feats": 1, "ranks": 1}` — what `creation` and the sheet's rank check read instead of the name |
| `traits[]`, `languages[]`, `description` | prose the forge shows |
| `not_yet[]` | what the sheet has no reader for, said rather than dropped |

Computed, never stored: `rp` (from the parts), `power` (standard / advanced /
monstrous), `trait_lines` (traits plus what the tags imply), `unpriced` (tags the table
does not know).

## The three laws, applied

- **One vocabulary.** The race is `race.<id>`; senses and immunities are tags. Feat
  prerequisites ask `has_state("race.elf")`. No consumer matches the race string.
- **One applicator.** Modifiers ride `_buff_mods` beside worn gear and feats, through
  the same `_scope_holds` / `_when_holds` reader; nothing of the document is saved onto
  the character, so correcting a race on the bench corrects every character of it.
- **Severed tells.** A racial term names itself in the dice popup ("Elf +2") the way a
  feat does. No model authors a number: a world's people is priced from what its words
  map to, and a body the table has no line for becomes a `not_yet` sentence.

## From a World Bible world

`rules/races.py:from_world` reads `play.races[]` when the export carries it (contract
in `docs/campaign-format.md`; World Bible does not write it yet) and otherwise derives
one race per `PEOPLE` whose entry describes a body — World Bible writes its
`people_anatomy` section (Anatomy, Body, Senses, Lifecycle) for those and not for an
ethnic group of somebody else's body. The cue table `CUES` maps the words to the
table's lines: wings → `move.fly.30` (4 RP, and a `not_yet` because the engine moves on
the ground), echolocation → `sense.blindsense.30`, talons → `natural.claws`, a carapace
→ `natural.armor.1`, "small" → size small. Ability scores are the standard option,
placed by the player at the forge. The draft is flagged `converted` (the bench shows
"unreviewed") until somebody saves it.

A people without a body of its own is a **heritage**: the forge's heritage field offers
it by name, so a Nahyrin is a Nahyrin without becoming a separate race.

The Races bench imports a world's races as files (`POST /api/homebrew/races/import`),
so they can be corrected; the forge offers them in that world whether or not they were
imported, the bench's copy winning where one exists. The house rule `core_races` keeps
or hides the Core seven beside them; `race_rp` is the tier the forge accepts.

## Still open

- The engine has no fly, swim, climb or burrow speed, no natural attacks, no
  ferocity reader: the tags are granted and priced, the `not_yet` lines say so, and
  the readers are the next stage.
- Saves "vs enchantment" / "vs poison" wait on the save roll naming its cause; the
  `when` clause has no key for it yet.
- World Bible writing `play.races[]` — the memory `world-bible-next-export` carries the
  ask.
