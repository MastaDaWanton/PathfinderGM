# The three doors a place comes in by

Companion to `docs/places-8b-plan.md`, which settled where the party *is*: one
coordinate, `Actor.at`, a place id from `rules/places.py`, everything else derived.
This note settles where places *come from*. Built 2026-09-05/06 after the player asked
why a town whose paragraphs mention its docks had no docks, whether a friend's house
could become a base, and whether the alley behind the market could be a different alley
from the one behind the library.

## What the traditions do (and what they abandoned)

- **MUDs.** LambdaMOO's `@dig` and Evennia's `dig` create a room *by command*, with an
  owner and an exit from where the builder stands. A room described in passing does not
  exist; a room dug does, and stays. Nobody has abandoned this in thirty years.
- **Inform.** Rooms are declared off-stage and brought on when the story needs them; a
  room is never minted from the narration. The Recipe Book's "small number of named
  positions" is the same instinct that removed the free-text `Scene.spot` here.
- **Roguelikes.** Ground is generated *on entry* from a seed, so the same stairs lead
  to the same level. Persistent levels (NetHack) are the default; regenerating on each
  visit (early Rogue) was abandoned because the player could not plan around it.
- **Blades in the Dark.** The crew's lair is a sheet, not a room: what is done to it
  accumulates, and it has a keeper. That is a situation card here, not a place field.
- **Refused:** free-form place creation by the narrator (the 502 on an invented
  destination was exactly that), unbounded child places (Fate caps zones at two to
  four; `MOST_CHILDREN` is six), and a second store of positions.

## The doors

| Door | Source | Op | Id | Origin |
|---|---|---|---|---|
| The world's own words | a settlement's facts and paragraphs, matched against `IMPLIED` cue words | none; derived in `home_set` | `{loc}~urban:{slug}` | `world` |
| Founded | the player, from where they stand | `found` | `{parent}/{slug}` | `found` |
| Ventured | the player going into a kind of ground | `venture` | `{parent}/{kind}` plus seeded spots under it | `venture` |

**Door one** is derivation, not storage: the same location text gives the same spots
every session, up to `MOST_IMPLIED` of them, with exits both ways from the gate. A docks
the paragraphs do not mention is not added — the fixture's Vyrakon names its guilds and
ore and gets a guildhall and a mine head, and no docks.

**Door two** is `@dig`. The engine mints the id under the parent (so "the back alley"
off the market and off the temple are two places), refuses a name already in use, a
parent it cannot find, an owner who is not a person in the scene, and a seventh child.
The minted place goes into `Scene.founded`, the one stored exception to "derived, never
stored" — the player made it, so nothing can derive it — and is read back through
`places.for_scene`, the one derivation, so `Engine.places()`, the brief, and `travel`
all see it without a second code path.

**Door three** is the roguelike answer. `venture_set(parent, kind)` seeds off the
parent's id, so the sewers under the market are the same sewers next time and going
down twice mints nothing the second time. The way there costs the hours the kind says
through `survival.pass_hours` (the same body toll foraging pays), the party is moved in
through `travel` (the one mover), and half the time something lives there — from the
bestiary, by the ground's terrain, through `gathering.creature_for`, never invented.

## Keeping the GAS structure

- **One vocabulary.** Holding a place is a tag, `holds.place.<slug>`; ask
  `has_state("holds.place")`. The origin of a place is a field on the `Place`, not a tag,
  because places are not actors and carry no effects.
- **One applicator.** The owner's holding is an `ActiveEffect` with source
  `place:<id>`, origin `found`, granted through `Actor.apply_effect`; remove it and the
  tag evaporates. No `owner_of` map anywhere.
- **Severed tells.** Each op emits one tell: "Marra's house is a place now, off the
  market, held by Marra." The narrator dresses it; the claims scrubber refuses prose
  that founds or enters a place no tell backs.
- **Server authority.** The injectors in `gm/judgement.py` (`inject_found`,
  `inject_venture`) read the player's own sentence — "we set up our base at Marra's
  house", "I go down into the sewers behind the market" — and add the op; the model may
  also propose it. Either way the engine validates the name, the parent, the owner and
  the kind, and refuses with the fix named.

## Still open

- World Bible could ship places directly (`docs/campaign-format.md` says nothing about
  them yet); door one is the bridge until it does — the memory
  `world-bible-next-export` carries the ask.
- A base's card accumulates facts but grants nothing; `Card.grants` is there for the day
  a fortified base should grant `cover.*` to those inside it.
- Venture spots are named from a fixed table per kind; the world's own words could
  sharpen them the way door one sharpens a settlement.
