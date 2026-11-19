# Hex travel on the region map: the plan

Status: **plan only, nothing built.** Written 2026-11-18 from the owner's idea and rulings
(memory `hexcrawl-region-map`). Branch `plan/hexcrawl`, off master 2963f4b9 (0.4.3).

## The idea, in the owner's words

Looking at the 3D tabletop region mock (`mock/place-map-v2`, `tabletop.html?level=region`):

> "we have all this unused space and we have hexagons we could have this level be used to
> travel as well and perhaps this could be used to generate more content in an area. if i
> wanted to search in the wilderness i could click on an adjacent hex and it would spawn a
> new area with something in it."

> "you can move 1 hex at a time you get a perception check which has the chance to spawn
> something more meaningful to an adjacent hex and if you find something a model is placed
> on the hex"

## The owner's rulings (2026-11-18)

1. **Clicking a neighbouring hex moves you there.** One hex at a time.
2. **Moving costs the book's travel time, and that is the only automatic time.** Inside a
   hex, time passes only as the player spends it (foraging, hunting, living off the land,
   going into a place, fighting). There is no fixed "explore for two days" block.
3. **Entering a hex gives a Perception check** that can reveal something meaningful in an
   adjacent hex. If it is found, a model is placed on that hex.
4. **Never nothing.** Every hex gives something usable; about one in three holds a real site.
5. **Hexes are 12 miles across.**
6. **100 XP for an explored hex** (+25 for difficult terrain or a hazard: the book).
7. **Terrain by rule now, and a World Bible ask** for real terrain and coordinates.
8. **On foot, one hex a move; on a horse, two** (2026-11-19: "if you are walking/running you
   can only move 1 hex at a time but if you have a horse you can move 2 hexes").
9. **No Perception check for the hex ridden through** (2026-11-19).
10. **A hex that has been Perception-checked looks different on the board** from one that has
    not (2026-11-19).

## Prior art this stands on

Read 2026-11-18. Primary where it could be reached.

- **Ultimate Campaign, Exploration** (legacy.aonprd.com/ultimateCampaign/campaignSystems/exploration.html):
  - the 12-mile hex;
  - travel through one hex at 30 ft speed: **5 hours on plain, 8 hours on anything else**;
  - full exploration 1 day plain or hill, 2 desert/forest/marsh, 3 mountain (**not used**:
    ruling 2 replaces it);
  - a landmark is found automatically on entering, or **from an adjacent hex with an hour and
    DC 10 Survival**. Hidden sites carry their own skill and DC. Ruling 3 is this rule, made
    Perception and free on entry;
  - 100 XP per explored hex, +25 difficult terrain or hazard, up to 500 in hostile areas;
  - random encounters once a day, or once per hex when several are entered in a day:
    01-50 none, 51-60 hazard, 61-100 monster;
  - "the GM should never answer 'nothing'" (ruling 4).
- **The Alexandrian's hexcrawl series** (thealexandrian.net, tag hexcrawl): one keyed
  location per hex, wandering encounters on a separate table. Densely keyed hexes "break the
  abstraction". Gaps in the key mean the wrong scale.
- **Goblin Punch, "Hexcrawls kinda suck"** (2024): hexes blur together; players pick
  directions blind; huge maps cannot be specific. Fixes: fewer hexes, rumours of what lies
  ahead, barriers that make direction matter. Ruling 3 answers "blind direction" directly:
  every step can show you something to head for.
- **Daggerfall** (15,000 generated locations): its own programmer said players found the
  generated quests "too generic", "repetitive", "unrewarding". Bethesda moved to handmade
  content. **The warning this plan is built against.** A hex's site is generated only as a
  *kind*. It is built from the world's own material (its nations, peoples, dungeon tags,
  bestiary ground, danger ratings) through doors that already make good content.
- **Owlcat's Pathfinder: Kingmaker**: overland travel ate the playtime; its random
  encounters were small and lootless "time wasters". So the move's encounter roll uses the
  group budget (up to three, APL -1 lone), never a token fight.
- Could not confirm from the books: Forbidden Lands' journey rules (only fan summaries
  found), and how Owlcat's map reveals hidden places.

## What already exists (reuse, do not rebuild)

| Need | Already there |
|---|---|
| The board | `mock/place-map-v2` tabletop (Three.js r170, Kenney CC0 kits): hex grid at 12 miles, fog, town and site levels, the player's figure, walk animation |
| City positions | the mock's `worldLayout` (shared/model.js): a force layout over road miles. **Computed in JS, not world data.** |
| Terrain of the town's own wild ground | `play/exits.py`, `rules/outskirts.py` (the woods, the cave, the desert at their hours) |
| Ground gone into | `Engine._op_venture`, `places.venture_set` (seeded off the parent id: same stairs, same cellar) |
| Dungeons and their story | `rules/dungeons.py` (tags, rooms, bosses who keep their lair) |
| Creatures of the ground | `gathering.draw_for` (bestiary ground, encounter budget, groups up to three), `ontheway._the_land` |
| Encounter budget | `rules/encounter_budget.py` (APL; lone PC -1) |
| Body over hours | `survival.pass_hours`, `Scene.advance(charge_body=False)` |
| Living in the wild | `live_off_land`, `hunt`, `forage` (by biome) |
| The player's roll | `_NeedsPlayerRoll` (the dice popup), as `track` and `forage` use |
| Danger of a place | `rules/volatility.py` (World Bible's 0-4 rating, ask 16) |
| Fog rule | `play/places_found.py` (one way beyond every place stood in) |

## The design

### 1. A hex is engine state, seeded from the world

- **New module `rules/hexes.py`.** Axial coordinates `(q, r)` at 12 miles.
- **Layout.** Port the mock's `worldLayout` to Python, then **store the result on the campaign
  the first time it is needed** (the campaign overlay, as the world's own data stays
  untouched). A later World Bible export that adds a town would otherwise move every hex
  under the player's feet. Stamp it with the layout's version, per CLAUDE.md's cache rule.
- **A hex record** is derived, never authored by a model: terrain, the nation it lies in, its
  site (kind, find DC, the place it opens), and what the player has done there (`seen`,
  `entered`, `searched`, `explored`).
- **Generated from a seed** of the world seed and `(q, r)`, so the same hex always holds the same
  thing. Only touched hexes are saved: a list of `{q, r, entered, searched, explored, spotted}`.
- **The fog stays a view** over these records, never world data.

### 2. Terrain by rule (ruling 7)

- **Known ground first.** A town's hex is its town. The town's own wild places put their
  terrain on its hex and its neighbours, as the mock does.
- **The rest by the nation's ground.** A deterministic noise over the nation's biome mix
  (forest, hills, plain, marsh, desert, mountain, water) from the world seed. Water hexes are
  coast and sea.
- **Rivers.** A river hex counts as water for `live_off_land` (CRB p.107; the 2026-11-18
  wilderness work already counts woods and rivers).
- **World Bible ask 33** (next free number; see §8) replaces the rule when it lands.

### 3. Moving one hex, or two mounted (rulings 1, 2, 8)

- **New op `hex_move`** (`CODE_ONLY_OPS`: written by the map click, never by a plan), with
  `to: [q, r]`. Refused unless the hex is in reach, is land (sea hexes wait for ships), and
  the party is out of a fight.
- **Reach (ruling 8):** a neighbour on foot; up to two hexes when the whole party rides.
  "Rides" is the journey's existing test (`journey.MOUNTS`: a horse, pony, mule, camel or
  riding dog owned on the sheet, bought or hired), so a mount bought at the stables counts
  on the board as it does on the road. One rider short (a companion on foot) and the party
  moves at the walker's pace, as a journey does. On foot, running changes nothing: the
  book's overland run is a hustle, and the owner's ruling gives it no extra hex.
- **A two-hex move goes through a hex.** The board shows the two-away hexes the ride can
  reach; the route is the straight line, or, for the six two-away hexes that sit between two
  neighbours, the cheaper of the two (land before water, plain before rough). The hex passed
  through counts as **entered** and gets its own encounter roll (UC: once per hex). It gets
  no Perception check (ruling 9): the check is made only where the party stops, so a hex
  ridden through stays unsearched on the board until a check covers it.
- **Time:** Ultimate Campaign's travel through one hex at 30 ft: plain 5 hours, anything else
  8. Mounted, each hex costs half that (the owner's Q13 ruling, `journey.PACES`: riding halves
  the time, the same multiplier for every mount), so a two-hex ride takes the hours of one
  hex on foot. The book roughly agrees (CRB Table 7-8: 30 ft is 24 miles a day, a horse's
  50 ft is 40). A gallop (Q13's third) is not on the board; it can come later as three hexes
  with the journey's horse fatigue. Paid through `survival.pass_hours` and `Scene.advance`, like a forage, so thirst,
  hunger and the awake clock all run. **This is the only time that passes on its own.**
- **Encounter on the way:** one roll per hex (UC: once per hex when several are entered in a
  day). Creatures come through `ontheway._the_land` / `gathering.draw_for` at the party's
  budget. The book's 10% hazard band has no hazard system to land on yet: **owner call**
  (proposed: folded into "none" until hazards exist).
- **Where the party stands:** a new place-id grammar for open ground, for example
  `{nearest settlement}~{terrain}:#q,r`. It hangs off the nearest settlement so its nation,
  coin and law still answer. **Owner call** (alternative: a free-standing `hex:q,r` location).

### 4. Spotting the neighbours (ruling 3)

- **On entering**, one Perception check: the player's roll, through the dice popup.
- **Each neighbouring hex's site carries its own find DC** (UC: hidden sites have their own):
  about 10 for what shows from far off (a tower, smoke, a ruin on a hill), 15-20 for what
  hides (a cave mouth, a camp under trees). Terrain and light shift it, as tracking does.
- **One roll is read against all six neighbours.** A success marks the site `spotted`, says what
  is seen in the tell ("smoke rises from the hills to the north-east"), and **places its model
  on that hex**.
- **Spotted is kept.** The model stays, and a site can be spotted from several sides.
- **Searched is kept too (ruling 10).** Every hex a check was read against is marked
  `searched`, whatever the roll: the hex stopped in and its six neighbours. (Counting the hex
  stopped in is our reading: the check is made from it, and otherwise a site in your own hex
  could only be found from next door.) A hex searched with a low roll can still hide a site;
  a later check from another side reads against it again, as the book's hidden sites allow.
- **The town's own landmarks** (a town, a road) are seen without a roll, as the book's
  landmarks are.

### 5. What a hex holds (ruling 4)

- **Every hex, the ground itself:** forage, hunt and live off the land by its biome
  (already built). Water by terrain.
- **About one in three, a site**, rolled once from the hex's seed:

  | Site | Built through |
  |---|---|
  | A ruin with a way down | `venture` + `dungeons` (a tag from the dungeon story; its boss keeps the lair) |
  | A lair | `gathering.draw_for`, guarded |
  | A camp of the world's own people | the codex people, `openings`/`schemes` (bandits, hunters, pilgrims, a hermit) |
  | A rich patch, a seam | the gathering excursions' `rich`/`guarded` finds |
  | Water worth the walk | a spring or pool place, free water for `live_off_land` |

  Weighted by the nation's danger (`volatility.scale`) and the terrain. The site is a **place
  document**, the same shape World Bible will write (memory `world-bible-next-export`: one
  format, two authors), so an authored site can stand in for a rolled one.
- **Going to a spotted site** is a move to its hex, then a walk into the place it opened.

### 6. Explored, and its XP (ruling 6)

- **Proposed definition (owner to confirm):** a hex is explored when the party has entered it
  *and* reached its site, or, in a hex with no site, spent at least an hour there doing
  something. That matches ruling 2: exploring is what the player does, not a timer.
- **The award:** 100 XP (+25 if the hex has difficult terrain or a hazard), once per hex,
  through the engine's XP door from a `rule:` origin (a model never mints XP: ponytail audit
  #22).

### 7. The board in the game

- **Prerequisite:** the owner has not picked a map direction yet. This needs at least the
  tabletop's **region level** in the game (Three.js is already vendored in the mock). The town
  and site levels can follow later.
- **The board reads engine state**, from a new `/api/hexes` (terrain, fog, spotted models,
  the party's hex) and posts `/api/hex/move`. The Perception roll comes back as the usual
  `awaiting` popup.
- **Models:** the Kenney hex kit's buildings for sites (tower, ruin, mine for a way down,
  tents for a camp), a primer-grey miniature when spotted, painted once visited (the mock's
  existing seen/visited idiom).
- **Searched hexes look different (ruling 10).** Three looks, from the hex record alone:
  *fog* (never seen), *seen but unsearched* (terrain showing under a light haze; this is how
  a hex ridden through looks), and *searched* (clear, full colour). The look must read at a
  glance on both themes and survive the worst-case toggle; the exact treatment is a design
  pass at build time (memory `ui-design-skills-preserve-look`: keep the board's colours).
- **Packaged build:** must work in the desktop app, not only under runserver (CLAUDE.md).
  Hit-test the board in the packaged build (memory `release-hit-test`).

### 8. World Bible ask (ruling 7)

Ask 33 for `docs/for-world-bible.md`, in the existing format, added at build time with the next
free number:

> **33. Coordinates and ground on settlements and regions.** Each settlement's map position
> (x, y in miles on its continent), and per nation the share of each biome (forest, hills,
> plain, marsh, desert, mountain, water), plus rivers as lines. Optional: without it the app
> lays the map out from road miles and invents ground by rule from the world seed. Rule 1
> holds: positions and miles, never hours.

## Build order

| Phase | What | Done when |
|---|---|---|
| 0 | Region board in the game (owner's pick of the tabletop) | the region renders from engine data in the packaged build |
| 1 | `rules/hexes.py`: layout stored on the campaign, terrain by rule, neighbours, travel hours | the same world and seed give the same board twice; a new town in the export moves nothing |
| 2 | `hex_move`: time, body, one encounter roll per hex crossed, two-hex reach when mounted | a move costs 5 or 8 hours a hex on foot, half that mounted, and nothing else passes; a fight comes at the group budget |
| 3 | Spotting: Perception against the neighbours' DCs, `spotted` and `searched` kept, searched hexes drawn apart | one roll reveals 0-6 sites; a model stays on a spotted hex across reloads; a searched hex looks unlike an unsearched one in the packaged build |
| 4 | Sites through the existing doors | over 300 seeded hexes, ~1 in 3 has a site; every site opens a real place; no kind is more than half |
| 5 | Explored + XP | 100 XP once per hex, never from a model |
| 6 | WB ask 33 | the ask is in `docs/for-world-bible.md` |

## Tests to write (each docstring names the defect it prevents)

- **Same hex, same site:** reloading or re-entering never re-rolls a site (Daggerfall's
  re-roll farming).
- **No automatic time:** moving costs exactly the travel hours; standing in a hex costs nothing
  until something is done (ruling 2).
- **Searched:** a stop marks the hex and its six neighbours searched whatever the roll; a
  hex ridden through is entered but not searched, and the board draws the two differently
  (rulings 9, 10).
- **Reach:** on foot a click two hexes away is refused; a mounted party reaches it in the
  hours of one hex on foot, crosses the hex between (entered, one encounter roll), and a party
  with one member on foot is refused it (ruling 8).
- **Spotting:** a natural 1 can still spot a DC 10 tower when the modifier carries it.
  Perception below every DC reveals nothing, and the tell says nothing was seen.
- **Grounded sites:** every site's place, people and creatures exist in the world, codex or
  bestiary (CLAUDE.md "ground every name").
- **Never nothing:** every land hex answers `live_off_land` and `forage` by its biome.
- **XP once:** exploring a hex twice pays once; no plan op can award it.

## Risks

- **Sameness.** The dungeon tags are 33 situations; a long walk will repeat them. Weight by
  nation and danger, never repeat a tag within N hexes, and say so in a test.
- **Content density vs the "1 in 3".** Measure it on both shipped worlds before trusting it.
- **The reader's prompt is at its budget** (0.4.3 already cut a demonstration to fit). Hex
  moves are clicks, so they add no act. Typed directions ("I head north-east") would need
  one: a later phase.
- **Road journeys and hexes.** A journey between towns crosses hexes. Phase 2 leaves journeys
  as they are and only updates the party's hex at the end. Spotting along a road is a later
  question, and must not fight `feat/travel-pacing`.
- **Sea hexes** wait for ships on the board.

## Owner calls still open

1. **Explored:** entered and site reached (or an hour spent where there is no site)?
2. **The book's hazard band** (10% of encounter rolls) has nothing to land on: fold it into
   "none" for now?
3. **Where open ground hangs:** off the nearest settlement (its nation, coin and law), or a
   free-standing hex location?
4. **Phase 0:** pick the region board (the tabletop in the screenshot?) so the board can be built.
