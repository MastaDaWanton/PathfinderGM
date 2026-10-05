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

## A place's own ground (2026-10-05)

The owner: "on a mountain still considered farmland". `found name="the mountain"` off the
road to Grotburrow took the road's farmland, because `mint` gave every child its parent's
ground; the header, UNDERFOOT and the narrator's absent-ground repair all followed the id,
and the repair, offered "close by, farmland, mountain, desert", wrote a desert sun.

- **Prior art.** A CircleMUD room carries its own sector type, one required value from a
  closed list, never inherited from its zone (Builder's Manual, World Files). Hexcrawl
  generators default a sub-hex to its hex's dominant terrain and let a feature inside it
  differ (DIY & Dragons, "Sub-Hex Crawling Mechanics" part 2). Fate puts aspects on each
  zone.
- **Rule.** `found` reads the place's ground from its own words through
  `places.PLACE_GROUND`, a closed lexicon onto `biomes.BIOMES` (`places.own_ground`): the
  kind when the kind is ground ("mountain", accepted by the validator now rather than
  refused), else the name, else `about`. A building's name ("the Forest Inn", "the hut on
  the hill") and a name with no ground word stand on the parent's ground. Never `urban`.
- **The id.** Off outside ground, the child keeps the parent's whole spot under its own
  ground's head — `~mountain:@the-road-to-…/the-mountain` — so it still parses outside, on
  that road, with no wilderness grafted beside it. Ventures keep their old seeded ids.
  Open ground is never `under` a town (`setting_of`). Open ground founded off a town room
  hangs off the outskirts, as a building hangs off the street.
- **The world decides.** Ground the settlement's land lacks is refused as a travel onto it
  is (`_absent_ground`); ground beyond the near land is as far as the world puts it, so a
  founded mountain beyond Vormoor's farmland costs the hours a `travel biome=mountain`
  would.
- **The narrator.** The tell states the ground; the brief prints `GROUND at <place>`
  whenever it is not the streets; the absent-ground repair names the ground underfoot and
  no longer offers the whole land list.

## The hinterland (2026-10-05)

The owner: "in the campaign im playing everywhere has been farmland i have not found a
single place that wasnt farmland outside of the urban city. this makes gathering tha
materials i need for crafting impossible."

**Measured.** On the click path (the Places row, `outskirts.ring` walked from the
outskirts by `places.route` and `outskirts.hop_minutes`), from Vormoor every place was
farmland or the shore: the outskirts, three road heads, the crossroads and the fields.
There was no forest and no hills. The nearest other ground was the badlands, 8 hours
out, and the mountain, 16. Settlements listing no open ground but farmland and the shore
within four hours:

| World | Settlements with none |
|---|---|
| Aurvantis | 15 of 64 |
| Pangrella | 0 of 12 |
| synthetic | 4 of 6 |
| the owner's Fantasia | 7 of 36 |

The cause was `geography.land_around`. `near` held only the first ground each road
crosses (farmland, on every Drossakar road) and the settlement's own land facts. Every
word of the region the settlement sits in went to `beyond`, at twelve miles: Drossakar's
"iron-rich badlands" and "volcanic ridgelines". The village was treated as standing
outside its own continent.

**Prior art.**
- Chisholm, *Rural Settlement and Land Use*: arable falls off from about a kilometre and is
  "exceptional" beyond three or four. Settlements of more than 5,000 farm out to 6–11 km
  (after Morgan 1969).
- Vita-Finzi and Higgs (1970), via secondary summaries: farmers' site catchments are drawn
  at 5 km, about an hour's walk.
- Inside that hour lay more than fields. Domesday England was about a third arable (this
  figure is attributed to Rackham; the attribution is not confirmed). Urchfont's pasture,
  coppice, arable and sheep down all lie within about 2.5 miles of the village (VCH Wilts
  10). Von Thünen puts wood in the second ring.
- Hexcrawls:
  - The Alexandrian wants "two or three different types of terrain immediately adjacent to
    the home base".
  - *Ultimate Campaign* counts a mixed 12-mile hex as its commonest terrain. That is this
    defect, one level down.
  - Welsh Piper's terrain-affinity table makes neighbouring ground mostly the same, then
    a secondary type. It is a generator; this app has a world to read instead.
- Games: Dwarf Fortress players embark where biomes meet. Valheim's Meadows always has the
  Black Forest within walking range.

**Rule.** `Land.reaches` (`geography.Reach`) is a settlement's hinterland: at most four
named stretches of open ground, each a ring place `{loc}~{ground}:@{slug}` with its own
ground and its own `Place.miles`.
- Its own close ground (roads' first ground, its own facts) lies at 3 miles, the hour
  `travel` always charged.
- The ground its **nearest** region's land facts name lies at 4 (village), 5 (town) or
  7 (city) miles.
- Reaches hang off the fields where there are fields (the waste lies past the
  ploughland), otherwise off the outskirts.
- `hop_minutes` prices a reach at its miles over its ground's road column. Vormoor's
  ridgelines are about two hours away and the badlands nearly three.
- `travel biome=hills` goes to the reach of that ground, so the spoken path and the
  clicked path land on one place.
- The Places row lists the reaches with their times, and the brief prints them under
  "within a walk".
- `terrain_of` is unchanged: the ground is in the head of the id, as for every place.

**What the world says, and nothing else.**
- Every reach's ground is a word the world wrote. Nothing is added because villages
  usually had a wood, so a desert world stays desert.
- Ground a road crosses only after other ground stays where the road puts it. Vormoor's
  mountain is still 16 hours away. Further out stays further.
- Three readings of the world's sentences keep ground the world put somewhere else out of
  the hinterland:
  - A clause that localises its ground: "salt marsh along the southern shore".
  - Ground qualified by another people's proper name: "Kyropticus deserts".
  - A list that spans a whole climate: "scorched badlands, … arctic tundras". Neither side
    is near.
- "ridgeline", "ridge", "foothill" (hills) and "hanger" (forest) joined the ground
  lexicon. "Canyon" did not, because the book has no canyon terrain.
- An export's `landforms` (docs/from-world-bible.md) replaces the derivation outright.

**After.** Settlements listing no open ground but farmland and the shore within four
hours:

| World | Before | After |
|---|---|---|
| Aurvantis | 15 of 64 | 3 of 64 |
| Pangrella | 0 of 12 | 0 of 12 |
| synthetic | 4 of 6 | 1 of 6 |
| Fantasia | 7 of 36 | 0 of 36 |

The mean number of distinct herbs and mined materials on that ground also rose, against
master 68a7758:

| World | Herbs before | Herbs after | Mined before | Mined after |
|---|---|---|---|---|
| Aurvantis | 41.0 | 64.4 | 8.0 | 13.0 |
| Pangrella | 59.7 | 77.8 | 2.3 | 10.2 |
| synthetic | 25.7 | 81.2 | 1.2 | 4.8 |
| Fantasia | 78.9 | 99.6 | 0.9 | 5.9 |

The settlements still without are honest. Their roads cross farmland first and the
hills or the woods only after, and their region names nothing else. Kestwick's downs, for
example, are half its road to Brindle Ford away.

**Still thin.** Drossakar is badlands and ridges, and the forage tables give hills and
desert 5 and 1 herbs against forest's 106. Vormoor's crafter now finds ore within a walk.
Herbs there are thin because the herb tags are, not because the ground is.

## Heard of: the state between a name and a place (2026-10-03)

The owner's ruling of 2026-10-03, asked how a place an NPC names should be handled:
"places must be creatable for example peoples houses". A fixed map is ruled out. What was
missing was the middle state. In the owner's items save the clerk said "make your exit
through the side door, past the smithy". Nothing recorded the smithy. "Head for the side
door" then had the planner found *the smithy* wherever it could, after a refused travel.

- **Prior art.** The traditions keep three states, not two:
  - Inform's Epistemology (Eric Eve, Recipe Book §5.5): *seen* and *familiar*, where
    familiar means known about but not found.
  - Skyrim draws a place you were told of as a grey marker, and you cannot travel to it
    until you have been there.
  - Morrowind keeps no marker; it writes the speaker's directions into the journal,
    relative to landmarks the player already knows.
- **Recorded** (`play/aftermath/places_heard.py` → `rules/heard_places.py`):
  - from an NPC's own line, never the narration;
  - only a place this settlement's map does not answer;
  - with the landmark the speaker tied it to. That is a real place named beside it ("the
    tannery out past the docks"), or where they stand ("through the side door").
  - Kept on `Scene.heard_places`, saved, at most eight per settlement.
  - Somebody's house stays `call_on`'s.
- **Made real on the first visit** (`judgement.go_to_heard_place`): the player's words
  going there, or a travel the plan already wrote, become `found` under the landmark and
  then `travel`. This uses door two, so the place is an ordinary founded place afterwards.
  `found_parent` reads the same landmark when the model founds it itself.
- **Shown** to the planner and narrator as words (`gm/brief/heard_places.py`): "the smithy
  — off the counting house, as the clerk told it".

## Still open

- World Bible could ship places directly (`docs/campaign-format.md` says nothing about
  them yet); door one is the bridge until it does — the memory
  `world-bible-next-export` carries the ask.
- A base's card accumulates facts but grants nothing; `Card.grants` is there for the day
  a fortified base should grant `cover.*` to those inside it.
- Venture spots are named from a fixed table per kind; the world's own words could
  sharpen them the way door one sharpens a settlement.
