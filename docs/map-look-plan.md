# What still looks wrong on the map: plan

*2026-11-11, after the owner's market picture ("Merchants selling good at the market should
be by their merchandise at a stall. not standing in a circle around the player"). Branch
`feat/map-fixtures`. Nothing here is built unless it says so.*

## Fixed today: posts

- **Before:** everyone who came into a room was put at their zone's distance from the
  player (`Scene.place_by_zone`), so the market drew a ring of people around Kesst.
- **Now:** outside a fight a person stands at a post (`rules/fixtures.post_for`):
  - a market trader stands behind a stall of their own, one trader to a stall;
  - another keeper stands behind the counter (the bar);
  - everyone else stands at the least crowded table, hearth, barrel or stall front.
- **Who gets a post:** people already in the room when the party walks in (laying the
  ground, and the population door), and every keeper.
- **Who keeps the ring:** a fight, a spawn at a stated range, anyone `engaged` or `far`,
  and somebody the scene brings up to the player mid-scene. There the distance is the
  point: a thug stepping out of the crowd is 15 ft from the player, not at a stall. The
  first version gave everyone a post, and three existing tests caught it moving exactly
  those people.
- **The market has stalls now.** A new `stall` kind (a trestle counter under a red
  awning) types most of the market's and merchants' row's solid clumps.
- **Prior art:** Creation Kit furniture and idle markers owned by an NPC (a sandboxing
  NPC uses only unowned ones), and The Sims' smart objects advertising themselves.
- **Old saves heal** the next time the party walks in, because squares are cleared on
  leaving a place.

## Still wrong, in the order I would fix them

The owner's rule (2026-11-11) is that polish changes need a mock showing current against
proposed before the game changes. Items marked **mock** go through
`docs/mock/polish` first. Items marked **fix** are bugs, where the board shows something
untrue.

| # | What looks wrong | Why | The fix | Kind |
|---|---|---|---|---|
| 1 | Dashed "you can move here" outlines sit on top of the tavern gallery, so they read as walkway squares | Reachable squares hidden behind a raised mass are outlined above it so they are not lost | Show hidden reachable squares only while the pointer is on the board, as a ghost under the mass, the way hidden figures already are | fix + mock |
| 2 | A figure standing behind another figure is simply covered; only walls ghost what they hide | The ghost pass tests raised ground, not figures | Run figures through the same occlusion test; ghost at 60% | fix |
| 3 | Two people show the same initial (two Ts, two Vs in the market) | The plate is the first letter of the name | Give a second letter when initials clash in a scene ("Ty", "Tr"); the same rule on both boards | fix |
| 4 | A trader looks like a shopper: every bystander is the same white figure | The colour carries the side only, and a trader is a bystander | A small brass mark on a keeper's base (an apron band or a coin) without changing the side colours | mock |
| 5 | Stalls hold no goods | A stall is one kind with no trade | Draw goods on the counter by the keeper's counter id (cloth bolts, sacks, jars, ironware), a small closed table from `market.py`'s counter kinds | mock |
| 6 | Some stalls are L-shaped (three squares bent round a corner) | The market's solid clumps come from the floorplan's scatter, and fixtures name the geometry rather than move it | Leave saved rooms alone. Lay straight stall rows only for a market with no saved grid, and test that no saved position ends up inside a stall | fix, needs care |
| 7 | The master of the market stands at a stall like a trader | A keeper without a counter goes counter-first, then stall | The master's post is open ground near the middle (or a notice board when one exists) | fix |
| 8 | The wolf still reads as a block on legs | The quadruped is boxes | A lower, longer body, a head and tail at different heights, four thin legs; the same for the other beast forms | mock |
| 9 | The stone courses on two parallel walls a row apart start at different heights | Course phase is taken per face, not from world height | Anchor the course pattern to world z so every wall's joints line up | fix |
| 10 | No night: the market at midnight is lit like noon | The renderer is not told the time of day | Pass `scene.day_part`; at night dim the lamp, let hearths and lamps throw their own light, blue the ambient | mock (variant E has a C-night scene to start from) |
| 11 | Tavern patrons stand at tables rather than sit at them, and nobody is checked live behind the bar | Posts are new; only the market was checked live | A seated pose for someone posted at a table; check the tavern, the smithy and the library live the way the market was today | fix + live check |
| 12 | The fight pictures used made-up positions (an ogre half in the gallery, a figure off the edge) | No live fight was run after the figures changed | Run a real fight in the tavern and in the market with live turns and screenshot each round | live check |

## Order

1. **Fixes 2, 3, 7, 9.** Small; none changes the look the owner chose.
2. **Fixes 1 and 11** with their live checks, then **check 12** (a real fight).
3. **One mock round** for items 1, 4, 5, 8 and 10 in the polish harness: current against
   proposed, the owner picks.
4. **Fix 6**, the stall rows, last and alone. It is the only change that touches geometry,
   so it carries the safety test that no saved position lands inside anything.

Each lane runs the whole suite, checks live in the running app, and merges nothing
without the owner's word.
