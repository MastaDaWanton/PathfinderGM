# Travel pacing and hex travel: one board, two layers (2026-11-21, feat/travel-pacing)

## Where the lane started

The lane was briefed to finish WIP commit e920bb65 (journey stretches, off 0.3.9). It was
already finished: feat/travel-pacing-2 re-applied it as 5a7eead2, then added 182134b1,
c76101b5 and 1d652414, and 0.4.3 "The Long Road" released it. That covers roads of three days
or more, a sea passage of about a fortnight, events in 3-day stretches, WB ask 32, the sea
table (island, wreck, survivor, pirates and others), and the cruise. So the branch reverts
the WIP (fa395a26) and merges master (7f25f59b). It does not rebase. A rebase would have
replayed a draft that master already holds in its later, reviewed form.

What was left is the owner's question: how the journey sits beside the hex moves added in
0.4.4. The prior art for the stretches themselves (Oregon Trail, The One Ring 2e, PF1e
Ultimate Wilderness, the Angry GM, Knave 2e, FTL, Sunless Sea) is in `rules/ontheway.py`'s
"the long way" docstring and is not repeated here.

## Measured before any change (master 0ede7c73, all three exports plus the owner's world)

| world | land legs | journey days (median, min) | hexes between towns (median, min to max) |
|---|---|---|---|
| Aurvantis | 152 | 4.0, 3.0 | 8, 4 to 13 |
| Pangrella | 12 | 4.3, 3.0 | 8, 5 to 9 |
| owner's fantasia | 26 | 3.0, 3.0 | 6, 5 to 10 |

Sea passages: median 14 days. The 3-day minimum belongs to rivers, which take the road floor.

At 8 hours a hex (rough ground), walking the hexes is quicker than the road on 6 of 190
legs, all in Aurvantis. At 5 hours a hex (plain the whole way), it is quicker on 56 of 190:
50 of Aurvantis's 152, 4 of Pangrella's 12 and 2 of fantasia's 26. The board's scale comes
from the world's raw road miles (`hexes.Grid.miles_per_unit`), and the road's 3-day floor
does not apply to it. So on open plain the hexes can beat the floor, at a far higher
meeting rate (one check a hex against the road's one a 3-day stretch). **Not changed
here.** Rescaling the board moves every hex under every save (`LAYOUT_VERSION`), and the
board belongs to the hex lanes. It is listed as an owner call.

Two defects, found on every world:

1. **Ground paid twice.** One hex out of town toward the next, then the journey: the journey
   still charged the whole road. In Pangrella that was 32 road hours, all of them, after the
   8-hour hex. Walking away from the town was the mirror case: the way back to the road was
   free.
2. **Two positions.** A journey set out from a hex "arrived" with the party still on the hex
   beside the town it had left, while the far town became its location. The cause is that
   `place_party()` takes the first place in the place set, and from a hex that set is the hex
   alone (`places._out_in_a_hex`).
3. A related slip, by reading the code: a journey stopped on the road showed on the board at
   the hex of the town it had left. So a hex move from there started beside that town's gate.

## Sources and what each says

- **PF1e, Ultimate Wilderness p.127** (aonprd Rules ID 2388, fetched today): checks four
  times a day at 20%, and "limit random encounters to one per day". It says nothing about
  roads changing the chance. That could not be sourced from PF1e at all.
- **Ultimate Campaign, Exploration** (from the hexcrawl plan's own reading, 2026-11-18): it
  gives the hours per 12-mile hex and checks once per hex. That is what `_op_hex_move`
  already does.
- **The Alexandrian, "The Layered Hexcrawl Part 2: Pointcrawl Layers"**
  (thealexandrian.net/wordpress/51277): it keeps a road pointmap and a hexmap of the same
  region in sync. The author finds running road travel through the hex procedure "awkward":
  you cannot really get lost on a road, the decision points become redundant, and tracking
  progress is fiddly. He goes back to the hex procedure only when the party leaves the
  paths. **The article gives no rule for joining or leaving a road partway, and none for
  avoiding double encounter checks.** Those parts are this app's own reading.
- **The Alexandrian, "Pointcrawls"** (thealexandrian.net/wordpress/48666, search summary
  only): pointcrawls are for civilisation and set paths, hexcrawls for open country.
- **Tabletop Kingmaker** (Paizo forum threads, a secondary source): a 5% check on entering a
  hex, plus 15% a day or night spent exploring or camping. So the AP also separates "moving
  through" from "spending time in" a hex.
- **Owlcat's Pathfinder: Kingmaker and Wrath** (Steam threads, players only): the token
  moves along fixed map paths until a random encounter or a rest. That is one position, on
  paths. The game's own rates could not be sourced.
- **The One Ring 2e**: a journey is counted in hexes on the map, and an event comes every 2
  or 3 hexes depending on the Guide's roll. That is from fan summaries; the Loremaster's
  Guide text on roads could not be read. It is the nearest precedent for measuring a
  journey on the board.
- **Blades in the Dark, Ars Magica**: neither search found travel rules. As far as I know,
  Blades cuts travel and goes straight to the engagement roll, but I could not source that.
  Nothing is built on either.

## Chosen

- **Road = journey, open ground = hexes, one position.** This is the Alexandrian's layered
  model. The journey keeps its stretches; a hex keeps its one check. Nothing new is rolled.
- **A journey from a hex joins the road by the board** (`Engine.road_share_left`). The road's
  hours are scaled by the hexes from the party to the far town over the hexes between the
  two towns. Hexes walked toward the town count as road behind the party; hexes walked away
  count as road to make up. Those hexes already paid their own hours and rolled their own
  checks, so the road's stretches roll only over what is left. This is our reading: no
  source gives a procedure.
- **Arrival is at the far town's way in**, whatever ground the party set out from.
- **A journey stopped on the road stands on the board** at the hex that far along the
  straight line between its towns (`hexes.along`, using Red Blob Games' hex line drawing). A
  water hex falls back to the town's hex. There are no coordinates in the export (WB ask
  33), so the straight line is the board's own geometry, not the world's road.

## Rejected

- **Running road journeys through the hex procedure**, hex by hex with a check each. The
  Alexandrian found it awkward, and at the road's per-hex rate a 4-day road would meet about
  2 things where the stretches meet 0.4. That brings back the tedium the owner ruled out.
- **Refusing a journey from open ground.** It is honest but punishing, and the exits row
  offers the road from everywhere.
- **Charging the walk back to the road head as hexes**, a second move before the journey.
  It is the same arithmetic as the share, done through extra turns.
- **A cap on the share.** Walking far away and then taking "the road" costs more road. That
  is true, and it cannot be gamed.

## Second pass

I re-read the Alexandrian article against the claims above. It does not cover joining a
road partway or encounter double-counting, and the note says so. The One Ring material is
marked as fan summaries. My first draft said the hexes were never a shortcut. Recomputing at
5 hours a hex as well as 8 showed that was true only for rough ground, and the paragraph
above was corrected.
