# Wild draws keep to the land's climate (playtest 2026-11-20 #20)

**Defect.** The road out of Branford (Kelmoria: "temperate, four clear seasons, reliable
rainfall") met two pyraustas. The pyrausta's Environment line is "any warm"
(Bestiary 5); `bestiary.parse_environment` already reads it as every land biome
(`biomes_any`) with `climates: ["warm"]`. Every land draw — `gathering.draw_for` (forage
encounters, hunting, a venture's inhabitant), `ontheway._the_land` (road, hex step, road
in stretches, the camp's night), `openings.foes_from_the_land` (an opening's fight from
the land) — called `bestiary.search(biome=...)` with no climate. Only the sea
(`ontheway._sea_meeting`, #89 the penguin) read one.

## Sources

- **PF1e Bestiary, Introduction** (legacy.aonprd.com/bestiary/introduction.html): the
  Environment line gives "the regions and climates in which the creature is typically
  encountered", often wider than the stat block's icon. So climate is half of the line,
  as binding as terrain.
- **PF1e Bestiary, Monsters by Terrain** (legacy.aonprd.com/bestiary/monstersByTerrain.html):
  the lists are terrain x climate band (Cold / Temperate / Warm); Coastline,
  Rivers/Lakes, Underground and Urban have no split. "Any Terrain" has an unqualified list
  plus Cold/Temperate/Warm sub-lists, so "any warm" belongs to the warm band only. The
  page warns there is "crossover ... especially between climate bands": behirs of warm
  deserts can turn up in temperate deserts but are much less likely in cold ones, and a
  monster out of its band wants an in-world reason. Lists are "a guide, not shackles".
- **AD&D 2e DMG, wilderness encounter tables** (discmaster mirror of the Core Rules 2.0
  CD, dmg/dd00551.htm): "have a separate table for each type of terrain", with arctic,
  tropical and other variants of the same terrain as separate tables.
- **AD&D 1e DMG, Appendix C** (table headings only, via a fan index at
  sites.google.com/view/advanced-dnd/random-encounters): separate tables for "Temperate
  and Sub-Tropical Conditions". I could not read the table contents themselves; only the
  split by climate is sourced.
- **Wilderness Hexplore** (OSR hexcrawl procedure, archive.org PDF): the temperate tables
  are the main ones, other climates' tables on a separate page — climate as its own layer
  over terrain. Seen in a search summary; I did not read the PDF through.
- **The Alexandrian, 5e hexcrawl part 5: encounters** (thealexandrian.net/?p=46192): has
  terrain shape each encounter's circumstances, and warns against over-specific designed
  tables (wasted prep, constant restocking). Checked on a second pass: the claim "start
  from one table, split by terrain only as needed", which a search summary pinned on
  this page, is NOT on it; I could not source it.
- **Baldur's Gate (CRPG)**: random encounters keyed to a handful of map areas, each with
  its own enemy list (fan wiki, search summary only — the page refused a fetch). The
  area stands in for both terrain and climate. Not confirmed from a primary source.

## Chosen

- One test, `bestiary.in_climate` (moved from `ontheway`, which keeps a delegate for the
  sea's test): a creature fits when its climates meet the land's, or either list is
  empty. Empty creature climates = unrestricted ("any forests"); empty land climates =
  the world said nothing, so nothing is filtered (absent is not none).
- One filter, `bestiary.of_the_climate`, the last step of all three land draws and of the
  sea's (the sea's `keep=in_climate` lambda is gone).
- One reading of a place's climate, `geography.climates_at(world, *place_ids)`: the
  place's settlement (`places.location_of`), its `land_around(...).climate` (read up the
  ancestors, where World Bible puts it: on the continent), and every band that prose
  names (`biomes.climates_in`, the word list the sea already used). A road takes both
  ends. "Hot days, cold nights" (Aurvantis's Sunkeep Reaches) is warm + cold: the
  creature lives in one of them, so a union never wrongly excludes. The sea keeps its
  stricter one-band-or-nothing rule for a crossing (`Engine._waters_climates`) but now
  reads words through the same `climates_in`.
- **Fallback when the band empties a window**: the next-door bands
  (`NEIGHBOUR_CLIMATES`: temperate <-> cold, temperate <-> warm), the book's own
  crossover; never the far band (warm creature in cold land, the book's "much less
  likely"). After that, nothing: each caller's existing ground-the-book-does-not-stock
  answer (travellers on the road, a quiet night or forage). Measured on the shipped
  book: across every biome x APL 1-8 x three bands (408 windows) the unrestricted
  creatures always keep the land's own band non-empty, so the fallback fired 0 times; it
  is there for homebrew books and narrow `keep` filters (a hunt's animals).
- "any" lines and multi-climate entries need no new code: `parse_environment` already
  expands "any" over the biomes and keeps the climate list, and a list of several bands
  is matched by intersection.

## Rejected

- **Widening to every band when the land's is empty** — reintroduces the pyrausta.
- **A weighted "crossover" chance on every draw** (sometimes a neighbour-band creature
  even when native ones exist): the book describes crossover as GM discretion with an
  in-world reason, which the engine cannot supply; and the weighting would be a number
  nobody sourced.
- **Validating the world's climate against the rulebook** or inventing a band for prose
  that names none ("mild and wet" is not mapped to temperate): the world owns its
  climate; an unnamed band is unrestricted.
- **Filtering dungeon-tag stock by climate** (`dungeons._spec_rows`): those are authored
  per concept, not drawn from the land, and the book's Underground list has no climate
  split. Left alone.

---

# At sea, only aquatic creatures and ships (owner ruling 2026-11-21)

## Part 1: what may be met at sea

**Defect, measured on the shipped book.** The sea's creature band (`ontheway._sea_meeting`,
the one path for a voyage's stretches and a held ship's cruise) drew from the `water` biome
kept by `open_water`, which read the Environment line alone: 74 creatures. One of them,
the living mirage ("any deserts or oceans", fly 20 ft., no swim speed), is not a sea
creature at all. Seven of the sea's own were left out because their line says "aquatic"
rather than "ocean": the dragon turtle ("temperate aquatic"), elasmosaurus and tylosaurus
("warm aquatic"), locathah, skum, charda, shoggoth.

**Sources.**
- PF1e Bestiary, Monsters by Terrain (legacy.aonprd.com/bestiary/monstersByTerrain.html,
  read in part 0 above): Ocean is its own terrain, split by climate band.
- PF1e aquatic subtype (aonprd.com/MonsterSubtypes.aspx?ItemName=Aquatic, seen as a
  search snippet on the second pass, page not opened): aquatic creatures "always have swim
  speeds" and breathe water. So the subtype implies the swim speed; the converse does not
  hold (a whale has a swim speed and no subtype).

**Chosen: line AND body.** A creature is met at sea when its Environment line puts it in
salt water (ocean, sea, saltwater, or "aquatic" not named beside a marsh, swamp, lake,
river or pond) and its stat block puts its body in the water (a swim speed in its movement
line, or the aquatic subtype). After it: 80 creatures; the mirage is out, the seven are
in, and the poison and giant frogs ("marshes and aquatic") stay out.

**Rejected.** The aquatic subtype alone: whales, dolphins and orcas carry no subtype, so
it empties much of the sea. A swim speed alone: every otter, frog and
crocodile swims. The line alone: the defect.

**Every sea draw path, grepped.** The voyage's stretches and the cruise both go through
`ontheway.sea_stretches` → `_sea_meeting` → `_the_land(keep=open_water, climates=...)`, so
the fix is `open_water`, once. The climate filter and its next-door fallback run after it,
inside the aquatic set. When nothing aquatic fits, `_sea_meeting` already turns the band
into a merchant: a ship, never a land creature. The shore, the coast and an island are
land (`coast` ground, the book's Coastline terrain): their draws are the land's and stay
so. Swimming out to a ship lying off (`Engine._swim_out`) draws no creature at all.

## Part 2: the navy patrol

**Sources (second pass marks what was read and what was a search summary).**
- Skull and Bones, faction hostility (wccftech.com/how-to/skull-and-bones-guide-faction-
  hostility/, read): attacking a faction's ships in view of others, or pillaging its
  settlements, raises a four-level hostility; at low levels its ships turn red only if
  you linger, at high levels they attack on sight; it falls by staying out of their sight.
  Rogue ships attack regardless.
- Assassin's Creed IV: Black Flag (Prima eGuide "The Wanted System" and dotesports, both
  refused a fetch; search summary only): the wanted level climbs one step per ship sunk,
  each step sends heavier hunter ships after the player, and bribing an officer clears it.
  An incognito ship is left alone. Not confirmed from the pages themselves.
- Sid Meier's Pirates! (search summaries only): a letter of marque lets you take a
  hostile nation's ships without becoming universally wanted; in the later eras navy
  warships patrol and governors grow less tolerant. How a nation's ship treats a ship it
  is at war with could not be confirmed.
- Sunless Sea (sunlesssea.fandom.com, search summary): most ships are hostile; neutral
  ships are rare, retaliate if attacked and are otherwise unresponsive; attacking them is
  piracy.
- Pathfinder (pathfinderwiki.com Chelish Navy, search summary): the Chelish Navy has "no
  tolerance for pirates" and runs pirate-hunting flotillas. Whether it inspects passing
  ships at the Arch of Aroden is, per the Paizo forum thread, never stated in canon. No
  PF1e rule for a patrol's treatment of a passing ship was found.
- UNCLOS Art. 110 (a warship's right of visit on suspicion of piracy) was going to anchor
  the inspection step; un.org refused the fetch and it is not claimed.

**Chosen: hail and pass, or run her down.** The common shape across the games is a
nation's ships ignoring a ship it does not want and hunting one it does. So the patrol:
- flies the flag of the nation of the port she sailed from or is bound for
  (`maps.nation_of`, a hidden die between two), a real name from the world, never
  invented; with no such nation the band is a merchant instead;
- is a real `warship` vessel record (`_keep_vessel`), named like every ship;
- hails and lets her go, unless the PC is wanted in any town of that nation, or the PC
  holds a ship whose seizure was sworn in one of its towns (`Vessel.sworn`, the existing
  "a master swore she was taken" record): then she comes about hostile, through the
  pirates' own machinery (`Scene.sea` with `hostile`, the chase, `_pirates_come_aboard`),
  and the people who come over the rail are marines from the codex (soldier, guard,
  sailor words), instantiated by `_defenders` as every crew is, not a number.

**Rejected or deferred.** An inspection step: the engine holds no contraband concept to
find, so an inspection would have nothing true to discover; that waits on a contraband
ruling. A notoriety ladder (AC IV's escalating hunters, Skull and Bones' four levels): the
engine's one standing with the law is per-town wanted or suspected, and a second scale of
it would be a parallel store. "Suspected" alone does not bring the navy down, by the same
reading the town watch gives it.
