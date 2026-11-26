# Research, lane fix/leave-the-dungeon (2026-11-26): owner asks A3 and A4

The owner's words are verbatim in `pgm-work/owner-asks-2026-11-26.md`. The save is a copy of
`owner-1126-data` (Shadow in the hall of pillars, below the tower on hex (-114, 76)).

## What the save shows (reproduced before any change)

- **A4.** The turn log holds four `hex_move` outcomes from the vestry and the hall of pillars,
  all `refused`, all with the same tell: "The day's travelling is done: eight hours on the way
  since the party last rested. Going on is a forced march: ...". The clock stayed at 4490 and
  the party at (-114, 76). No narrator ran: `hex_views._tell` only narrates when something
  resolved. The engine's refusal itself was the "narration". It went on the page as a GM
  paragraph straight under the player line "I set out north-east across the grassland." So
  "eight hours on the way" read as a day's walk that had just happened.
- On unmodified 3791c3f9, with a copy of the save, the move refused with that text: 200 and
  the same tell. With `march: true` it did **not** refuse. It asked for the Perception roll,
  and `_op_hex_move` would then have lifted the party out of the hall of pillars to the hex in
  one step (its `in_site` branch walks "up out of the hex's site"). So there were two defects:
  1. The wrong refusal was given first. The travel-day check ran before anything asked where
     the party stood.
  2. On a fresh day the move would have walked straight out of a dungeon, unasked.
- **History.** The refused move was also written into the model history as
  "(From the region map: I set out north-east across the grassland.)", the same line a
  successful move writes. The next narrator turn read it as a journey made.
- **A3.** `play/atlas.py` `_sites` sends the site's root (the tower) and its rooms. The place it
  lies under (the hex, `site.host`) is only a "Back up" arrow, and that arrow only changes
  which map is shown. Nothing on the Site map can be pressed to walk out. The engine's exits
  row did offer "the hills 24 miles north-east of Branford" from the hall of pillars. The map
  did not.

## Sources

- **PF1e, CRB Exploration Movement** (https://www.d20pfsrd.com/gamemastering/exploration-movement/):
  three scales. Tactical is "for combat, measured in feet (or 5-foot squares) per round".
  Local is "for exploring an area, measured in feet per minute". Overland is "for getting from
  place to place, measured in miles per hour or miles per day". The Region map is overland
  movement and a dungeon is local. The book has no rule for changing scale. That the party has
  to be out of the area before overland movement applies is my reading of these definitions,
  not a quoted rule.
- **Baldur's Gate (Infinity Engine)**, Beamdog forum threads
  (https://forums.beamdog.com/discussion/87685/steam-edition-cannot-travel-hit-a-wall-of-black
  and the comments linked from it). The world map can be opened from anywhere, but travel only
  happens by walking to an area's edge. Dungeons and buildings are separate interior areas. I
  could not find a primary design document; this is player reports plus the fandom wiki.
- **Pathfinder: Kingmaker** (gamerguides.com walkthrough pages; Steam discussions). An area
  has an exit marker: a compass rose returns to the global map, a door icon goes to a linked
  area. The exit is a thing drawn on the local map that you walk to. These are secondary
  sources, and I could not confirm them from Owlcat documentation.
- **NetHack** (https://nethackwiki.com/wiki/Escape_the_dungeon). You leave the dungeon only by
  climbing the up stair on level 1, after a confirmation prompt. The way out is a feature on
  the map itself.
- **The Alexandrian, hexcrawl series** (https://thealexandrian.net/wordpress/48051/roleplaying-games/hexcrawl-addendum-designing-the-hexcrawl).
  A keyed hex holds a location; anything bigger than a mini-dungeon "bump[s] it into a
  separate document". So the dungeon is its own map below the hex. I found nothing in the
  series on how to show the way back out.
- **What was tried and abandoned.** I found no tradition that let overland travel start from
  inside a dungeon and then dropped it. Every one I read keeps the transition at the exit. I
  am stating that as a lack of evidence, not as a finding.

## A4: decided

- **Below ground, a hex move is refused before any other check.** This covers a dungeon room
  (`origin` "dungeon") and underground terrain: the sewers and cellars under a town, and
  caves. The test is `Scene.underground`, which already answers this for light.
  - The tell names the room and the site above it.
  - It also names the way out, walked from the engine's own place graph (`places.route`) to
    the open ground: "Shadow is in the hall of pillars, below the tower, and the region map is
    walked from open ground. Leave first: back through the narthex and the tower to the hills
    24 miles north-east of Branford, then choose the hex again."
  - Under a town, the route ends at the place over the way down.
- **On the surface, a site is still walked out of by the move.** Standing in the tower's own
  floors or the ruins' gate, a hex click walks out first, as playtest 2026-11-20 #4 built it.
  - The hexcrawl ruling ("clicking a neighbouring hex MOVES you there") and that playtest fix
    settle this.
  - CRPG practice (exit at the area's edge) leans the other way. That is listed as an owner
    call.
- **The Region map shows the refusal.** `hexAct` puts the refusal tell into the map slip's
  "said" note, the same place a stopped walk is reported.
- **History.** A refused move goes into the model history as "tried and refused: ...". The
  refusal itself was already the only thing written on the GM side.
- **Rejected:**
  - Auto-walking the party out of the dungeon on a hex click. The owner asked to be denied,
    and that walk skips every room's doors and traps.
  - Rewording the travel-day refusal only. It was true; it was the wrong refusal to give
    first.

## A3: decided

- Each site sent to the page carries `out`: `{id, name, at}` for its host place (the hex, or
  the town place over the cellars).
  - It is only sent once that place has been stood in.
  - It is seated one column before the way in, on the way in's row.
- The Site board draws it as a slab of open ground with no walls and a step up, joined to the
  way in by a passage, with "Way out: <name>" on hover. The "Back up" arrow moves beyond it.
- Pressing it is a pick like any room's, so the slip is the chart's own, with Walk there.
  - Walk there attaches the place chip, and Say sends the engine the route through the rooms.
  - No new door or op was added. This is the same path the owner already used to walk to the
    tower from the death room (turn log 475).
- **Kept apart from `rooms`.** `siteOfRoom`, `posOf` and the room counts all read `rooms` as
  the site's own. Putting the hex in there would have made standing on the hex look like
  standing in the site.
- **Rejected:**
  - Making the "Back up" arrow walk. It is a view change everywhere else on the board, and a
    second kind of arrow would make it ambiguous.
  - A separate "Leave" button in the slip. The owner asked for a room on the map.

## Second pass

I re-read each source after writing the note:
- The CRB page's quotes match.
- The Baldur's Gate and Kingmaker claims are marked as forum and guide sources.
- The Alexandrian quote was re-fetched and confirmed: a mini-dungeon "represents pretty much
  the upper limit of what I'll handle in a hex key entry before bumping it into a separate
  document".
- The NetHack page was re-fetched and confirmed: climb the level 1 stair without the Amulet
  and answer "yes" when prompted.
- The claim that no tradition was found to abandon the exit transition is a negative, and is
  stated as one.
