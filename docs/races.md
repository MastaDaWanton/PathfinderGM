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

## The two worlds' own races

"can you make the specific races for the two worlds" (2026-09-06). Written by hand from
each export's own words, in `content/races/pangrella.json` and
`content/races/fantasia.json`, each carrying `world` so the forge offers it in that
world only. `rules/races.py:written_for` finds them; `for_world` offers them first and
drafts only a people nothing written speaks for; `heritages_from_world` offers only the
peoples no written race claims.

**Pangrella.** The continents name the species — "Winged: Kaelinorans, Flightless:
Kyrexi"; "Korvathyrans (winged), Kelvaxians (subterranean), Valtorians (flightless)" —
so those are the races, and the six `PEOPLE` entries are their cultures, listed on the
race as `heritages`: a Nahyrin is a Kaelinoran, a Zhilakai a Kyrexi, the Khra'gix,
Khy'vyr and Nirkor are Valtorian nomads. The Korvu, "descended from the earliest Kyrexi
migrants", have avian wings, talons and echolocation in their own entry and are a body
of their own. Flightless peoples take a human's option and budget; winged ones take
flight; the subterranean Kelvaxians darkvision and tremorsense.

**Fantasia.** All twelve peoples carry an anatomy, so each is a race, with the
evolutions its sentences support and nothing more: the Xylthys' "long arms ending in
webbed hands; webbed feet with sharp claws" and gills are swim, claws and breathing
water; the Brynkorovi's quadrupedal plan is an extra pair of legs, their "poor in
bright light" is light sensitivity, their vestigial wings are in the description and
nowhere else; the Vylkori's two to three metres stay Medium, as the Race Builder keeps a
player race, and the description says so.

## The anatomy: eidolon evolutions, free

"fix the race editor so that its all dropdowns and pickers because they should not need
to type anything other than a name. they can craft the anatomy from the Eidolon
evolutions free of cost" (2026-09-06). The Races bench opens a page of pickers
(`/homebrew/races/`): creature type, size, base speed, the Race Builder's ability
options (or a six-select fixed row), the bonus feat and rank, languages as checkboxes,
and the anatomy as the summoner's eidolon evolutions from the Advanced Player's Guide
— `content/races/evolutions.json`, 54 of them, each with the picker it needs (an
energy, a skill, an ability, an attack, an alignment) and how many times it may be
taken. An evolution costs no race points; the summoner's own figure is kept for the
record and shown on the card.

The stored document keeps `evolutions` as picked. `rules/races.py:expand` turns them
into the grammar every time the document is read — tags, modifiers, natural weapons,
the speed the extra legs add, the size — so correcting an evolution in the catalogue
corrects every race that took it, and nothing is saved twice.

### What the engine reads now

| Tag or field | Reader |
|---|---|
| `weapons[]` (claws, bite, gore, slam, sting, pincers, tail slap, tentacle, wing buffet) | `Actor.natural_weapon`: a weapon in the hand by the body's size, always proficient, reached by its name or an alias ("talons" are claws) |
| `immune.<energy>` | `Actor.immune_to` beside the stat block's printed line |
| `resist.<energy>.<n>` | `Actor.resistance`, the better of the printed and the tagged |
| `ferocity` | `Actor.apply_hp_state`: below 0 the body is staggered and dying, not unconscious |
| `move.fly|swim|climb|burrow.<ft>` | `races.speeds`, on the sheet's body block and in the narrator's brief as a fact of the body |
| `sense.*` | `races.senses`, the same two places |
| `proficient.simple|martial` | the existing proficiency question |
| `skill_mod`, `combat_mod ac natural`, `mods` | the one funnel, as before |

The brief's line — "A Korvu: moves by fly 30 ft as well as on foot; senses: blindsense
30 ft; natural weapons: claws." — is a tell about the body, with no number the engine
did not set, and the narrator may use it and may not contradict it.

Still waiting on a reader, said on each card's `not yet` line: the grid reading a fly
or swim speed as movement, reach, grab, trip, rend, rake, constrict, pounce, trample,
poison and energy riders on natural attacks, breath weapons, webs, damage reduction by
alignment, fast healing, spell resistance, frightful presence, extra arms.

## Still open

- The grid does not yet move a flier or a swimmer by their own speed; the speeds are
  on the sheet and in the brief, and the `not yet` lines above list the rest.
- Saves "vs enchantment" / "vs poison" wait on the save roll naming its cause; the
  `when` clause has no key for it yet.
- World Bible writing `play.races[]` — the memory `world-bible-next-export` carries the
  ask.
