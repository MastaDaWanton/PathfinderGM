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

## Done, 2026-11-12 (steps 1 and 2)

- **Fixes 2, 3, 7, 9, 1, 11** (0f2b8826, b8de2195, 19d682bc):
  - people behind people are drawn as ghosts;
  - initials get a second letter when two clash;
  - the market master stands off the stalls;
  - patrons sit at tables and stand up in a fight;
  - hidden-square outlines show only on hover.
- **Found while checking:**
  - a tavern founded in play got carts and crates (now a bar and tables);
  - a Large body spawned half inside the gallery;
  - `_sits` crashed with no fixtures.
- **Check 12, the live fights**, turned up four walk-to-a-fixture faults, all fixed:
  - 5a2bf0a5: "behind the bar" was read as the barrel; the player's words now pick the fixture.
  - 5a2bf0a5: a line grazing a low obstacle's edge gave +4 cover from everywhere.
  - 225e0e56: a walk in a fight must fit the round's movement and take a covered side. Before, all seven plans were refused, and then the PC stood in the open beside the foe.
  - 56642baa: "duck/slip behind X" is read as stealth; it now walks there first.
  - ad9051d3: the reachable square covered from the most foes wins, across every fixture of the kind (two foes on opposite sides refused the walk outright).
- **Live result:** in the market, "duck behind the nearest stall" moved the PC 30 ft behind a stall, the Stealth roll was offered and succeeded, and the board showed "Sneaking". In the tavern, rapier rounds resolved with legal squares on both boards.
- **Found, not fixed (not map work):**
  - the planner retries an illegal move seven times, then degrades;
  - "You draw your rapier" was narrated with no draw op;
  - a hidden PC's foe "swings blind" with a sap from about 40 ft without moving.
- **Judgement call for the owner:** a fight walk prefers cover from more foes over the nearest fixture. "The nearest stall" went to a stall 30 ft off that hid the PC from both thugs.

## Done, 2026-11-13 (steps 3 and 4)

- **Step 3, the mock round** (items 4, 5, 8, 10), on branch `mock/map-look` (fa6a23aa), built
  on this one, with the comparison page at `docs/mock/map-look/index.html`. The proposed
  looks are real game code on that branch, shot from the running game beside this branch's:
  - 4: a brass coin on a keeper's base (3D) and token rim (flat). A coin, not a ring,
    because a gold ring already means "whose turn".
  - 5: goods on a stall, read from the keeper standing at it (`keeps`, the counter id, now
    in the actor state); a stall with nobody at it is bare.
  - 8: a lower, longer beast with a raised head, snout, ears and a low tail.
  - 10: night from `Scene.light_at` as the PC sees it (`grid.light`), never the hour; dim
    is blue and darker, a carried torch lights its ring warm, a roofed room stays lit.
  - Item 1 was already fixed in step 2, so it was not in the round.
  - Waiting on the owner's pick. Nothing from it is on this branch.
- **Found during the round, fixed here** (c27d1833): four stallholders all read "SS";
  clashes left after the letter rules now number (S1..S4). Cinzel's "1" can read as "I".
- **Found, owner's call:** out of a fight a bystander is a brown disc on the flat board and
  a white figure in 3D, though the 3D code says the boards share colours.
- **Step 4, straight stall rows** (805ac18b): `floorplan._rows` lays a market's clumps in
  rows with 10 ft aisles and a gap between stalls, so no two can merge into a bent stall.
  A market saved before this keeps its stalls (`fixtures.derive` names it by the old
  scatter when that matches the saved grid better); nothing saved is moved. Live: the save
  loaded with its old stalls whole, then a walk out and back laid the rows, nobody inside
  anything. The merchants' row still scatters (not in the plan item).
