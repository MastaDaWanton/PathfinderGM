# Dungeon exits: rooms not yet found are not ways on (playtest 2026-11-20 #21)

## The defect, reproduced

Stood at a hex site's head with the way down found and its trapdoor still stuck, the exits
row (`play/exits.py`) listed every room of the dungeon as "a minute or two's walk", with no
`blocked` sentence on any but the first. Measured on Aurvantis (seed 3): the gatehouse
(shut, correctly) and then the guardroom, the armoury, the gnawing room and the feasting
hall, all open to a click. Pangrella and the synthetic world showed the same shape.

Cause: a hex site's places sit under the `@hex-…` root, and `places.is_ring` reads any
`@` root as a settlement's ring (the outskirts, the road heads). The row's "the rest of the
ring, by the walk `places.route` finds" pass therefore offered every dungeon room, routed
straight through the stuck trapdoor, because `blocked_for` asks the door check of the last
hop only. The engine's per-hop walk did refuse ("jammed"), so nothing walked past the gate,
but the row spoiled the names and offered the click. A venture off a town's outskirts (the
town dungeons of 0.3.7) has an `@outskirts/…` root and the same pass; a dungeon under a
town room (cellars, sewers) never reaches that pass. The fog-of-war chart
(`play/places_found.py`), the site map and the narrator's "ways on" (`gm/agent.py`) all read
the same `ways_from`, so they carried the leak too.

## Sources

- **SMAUG `do_exits`** (a Diku descendant), quoted at
  https://gammon.com.au/forum/threads/2914.html: an exit flagged `EX_HIDDEN` is skipped
  entirely; a closed exit is still listed (in brackets in the short form) and, in the long
  form, reads "Closed" instead of the room name beyond it.
- **DikuMUD3 zone manual**,
  https://wiki.dikumud.com/wiki/Manual:Zone_Manual/The_Room_Section/A_more_complex_set_of_rooms:
  doors carry `EX_CLOSED`, `EX_LOCKED`, `EX_HIDDEN` and a search difficulty. The exit list
  is the room's own exits, one step each; no MUD found lists rooms several steps away.
- **Inform 7, Exit Lister** (Gavin Lambert),
  https://rileypb.github.io/I7extdocs/10.1/Extensions/Gavin%20Lambert/Exit%20Lister-eg1.html:
  lists the current room's exits, a closed door marked "(closed)" by default. The visited /
  unvisited bit and `the best route … through visited rooms` (WI §6.14, already cited in
  `play/places_found.py`) is Inform's way of walking only through known rooms.
- **Brogue / NetHack** (already cited in `play/places_found.py`): cells are DISCOVERED or not;
  nothing undiscovered is drawn, and NetHack removed map amnesia, so knowledge only grows.
- **OSR procedure** (Errant SRD, Exploration Turns,
  https://funkaoshi.github.io/errantsrd/SRD/9-exploration-turns.html, and the OSE SRD's
  Dungeon Adventuring, which answered HTTP 500 on 2026-11-21 and was read only through the
  search summary): Errant has forcing a stuck door take one Exploration Turn, and the
  Guide gives "reasonably exact descriptions of the areas in which they find themselves",
  the players doing the mapping, so the map is built from where the party has been. The OSE
  summary says secret-door searches are rolled by the referee so the player cannot tell a
  miss from nothing there. I could not find a primary source stating "the referee names
  only rooms the characters can see" in those words; it is the practice these procedures
  imply, not a quoted rule.
- **PF1e**: CRB p.412 (doors: stuck/locked and break DCs) and p.413 (secret doors, DC 20),
  already the rules `rules/dungeons.py` cites. The CRB has no rule for what a closed door
  reveals of the room beyond it; nothing in it lets a character see through one.

## Chosen

The ring pass skips a dungeon room the party has not stood in (`Scene.been`), and skips any
place whose walk crosses a shut dungeon door (`dungeons.door_between` on every hop). A room
is still a way on one step from the room beside it (the row's `next_door`/adjacent pass,
which was always right), shown shut with the door's own sentence while its door is shut.
So a room joins the row the moment it is minted beside where the party stands (the way down
found), opens the moment its door gives (`break_door` sets `state` "open"), and the rooms
past it join when the party stands in the room they open from. Saves already carry all of
it: the rooms and their doors are `Scene.founded`, where the party has been is `Scene.been`.

## Rejected

- **Hide every room not in `been`, adjacent ones too.** Every tradition above lists the
  current room's own exits, closed ones marked; the module's own rule is that a way the
  rules refuse is shown shut with the reason, never hidden.
- **Treat `@hex` as not a ring.** Narrower ids would have fixed the hex site and left the
  outskirts ventures (same bug), and would have changed how a hex's open ground and spots
  are offered, which is fix/hex-travel's territory.
- **SMAUG's "Closed" in place of the far room's name.** The engine's own arrival tell
  already names the room beyond a door ("The trapdoor leads to the gatehouse; it is stuck",
  `dungeons.arrived`), so renaming only the row would disagree with the prose. Left as an
  owner call.

Second pass: re-read the SMAUG quote (gammon thread 2914) and the Errant page against the
claims above; the OSE claim is marked as read through a summary only.
