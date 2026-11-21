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
