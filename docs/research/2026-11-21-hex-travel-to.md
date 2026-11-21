# Click-to-travel on the region map — research note (2026-11-21)

Owner decision 2026-11-21: since fix/hex-scale the owner's ruins lie 3 hexes (36 miles) out
of Branford, and each hex took its own click. Making a click move 2 hexes on foot and 4
riding was rejected because it would skip the checks for the hexes it jumped. The decision
was click-to-travel: pick a seen hex and walk to it, one real hex at a time.

## Sources

- **Ultimate Campaign, Exploration**
  (legacy.aonprd.com/ultimateCampaign/campaignSystems/exploration.html).
  - Travel Time (1 Hex) table, re-read today: at 30 ft a hex takes 5 h on plain and 8 h on
    other ground. At 50 ft it is 3 h and 5 h.
  - The encounter table is rolled "once per day (or once per hex, if the PCs enter multiple
    hexes in a single day)". So the book expects several hexes in one day, each with its
    own roll. That is the reading built here.
  - The page has no rule for how many hexes fit in a day beyond the per-hex hours.
- **CRB overland movement / Forced March** (roll20.net/compendium/pathfinder/Movement;
  d20srd.org/srd/movement.htm for the 3.5 text it inherits).
  - "In a day of normal walking, a character walks for 8 hours."
  - Each hour past 8 is a forced march: a Con check, 1d6 nonlethal on a failure, and
    fatigued.
  - The engine already holds this day as `journey.HOURS_PER_DAY = 8`, and the journey
    splits its days on it. Reused; no new constant.
  - I did not open the CRB's Table 7-6 "24 miles a day at 30 ft" on a primary page today.
    It is quoted from docs/hexcrawl-plan.md, which cites CRB Table 7-8.
- **Red Blob Games, Hexagonal Grids** (redblobgames.com/grids/hexagons).
  - Line drawing is the cube lerp and round that `hexes.along` already implements.
  - For obstacles: "pathfinding on hex grids isn't different from pathfinding on square
    grids". Use A* or Dijkstra with the hex neighbour function, filtering out impassable
    neighbours. The simple flood-fill BFS is for movement range.
- **The Alexandrian, hexcrawl procedure** (thealexandrian.net, hexcrawl cheat sheets).
  - Travel runs one watch (4 h) at a time: direction, the encounter check, then the move
    into the next hex and a reset of progress.
  - The procedure is a loop the GM runs per unit of time. Players state a direction and a
    pace, never a teleport. Each unit gets its own check.
- **Foundry VTT modules** (foundryvtt.com packages: Lidarion Hexmap Studio, RTS Controls
  with routinglib, World Weave, Hexploration).
  - Core Foundry has no click-to-travel on hexes.
  - RTS Controls routes a token to a clicked point with routinglib's pathfinding.
  - Lidarion animates a party token hex by hex.
  - World Weave has players submit a route for the GM to approve.
  - I could not confirm that any of them stops a route on an event. Their pages do not
    say.
- **Roguelike / CRPG auto-travel** (already cited in `Engine._held_by_stopped_walk`):
  walk a computed path until something disturbs you, then hand control back.

## What was chosen

- **The route** is `hexes.land_route`: Dijkstra over land hexes only.
  - It optimises, in this order: the fewest hexes, then the fewest hours (plan §3: plain
    before rough), then the hexes nearest the Red Blob straight line.
  - Open country therefore walks the line the eye draws. Water is walked round, or the
    click is refused ("no way over land").
  - The search is bounded to 6 hexes of detour.
- **One machinery.** The walk is the existing per-hex step of `_op_hex_move`, wrapped in a
  loop of moves: one hex on foot, two riding (ruling 8). Every hex pays the same things:
  - its hours (halved riding, `journey.mounted_hours`);
  - the body toll (`survival.pass_hours`);
  - the road check (through `travel`);
  - entered and explored bookkeeping.

  The look (Perception, sightings, searched) runs where each move ends. That keeps ruling
  9: a hex ridden through gets no look. No second path was written. The old two-hex ride
  is now the same loop.
- **Stops**, on the hex where it happens:
  - a meeting: `travel`'s `met_refs`, so a toll-keeper stops it, not only a fight. Before
    this, a peaceful meeting on hex one of a two-hex ride did not stop the ride, despite
    plan §3;
  - a fight;
  - a refusal, or `travel` landing somewhere else (the watch, someone lying in wait);
  - a first sighting of a site;
  - the body giving out (`survival.pass_hours` collapsed, asleep or out cold). Added
    after the live check on the owner's save: a third walk through the night said "they
    could not keep going" and walked on;
  - the travel day.

  The tell ends "The walk stops on X, N hexes short of where you were going: <why>." A
  `hex_walk` effect carries the reason code.
- **The travel day**: the walk stops once its hours reach `journey.HOURS_PER_DAY`. A hex
  begun inside the day is finished. The day counts this click's hours only.

## Rejected

- **2 hexes / 4 hexes a click.** Skips the jumped hexes' checks and breaks the day.
  Rejected by the owner.
- **A pure straight line** (`along` only). It crosses sea hexes. Kept only as the
  tie-breaker.
- **BFS by hex count alone.** It gives no preference for cheap ground, and the old ride
  already sorted plain before rough.
- **A dice popup for every look on the walk.** That is the clicks this feature exists to
  remove, by another name. The first look is the player's popup die. Each later look is
  the engine's own d20 with the same modifiers, shown in the tell. **Owner call.**
- **Strict no-overrun day** (never begin a hex that would end past hour 8). On foot this
  makes every day one hex: 5 h or 8 h, and a second 5 h plain hex would make 10. A walk
  would then never get past its first hex, the same as before. The UC table's hours are
  coarse (12 miles at 3 mph is 4 h, the table says 5). Finishing the hex begun gives two
  plain hexes a day on foot, the CRB's 24 miles, with no forced-march check. **Owner
  call.**
- **Counting the day across clicks** (hours since the last sleep). The engine keeps no
  "travelled today" record outside a journey. The awake clock and the body toll already
  charge a party that clicks on into the night. Left for later. **Owner call.**
- **Validating fog on the server.** The fog is a client view
  (`places-board.js`: roads, wild places, touched hexes). The server checks land and a
  land route. The board offers only hexes not under cloud.

## Second pass (re-read of the sources against the claims above)

- **UC "once per hex"**: confirmed verbatim on the page.
- **UC table**: confirmed. It is titled "Travel Time (1 Hex)", not "Table 3-2"; the code
  comment's name comes from the print book.
- **Red Blob**: the page's line-drawing section body did not come through the fetch. The
  `along` implementation comes from the earlier hexcrawl work, so "line drawing" is
  cited from there, not re-verified today.
- **Foundry**: the claim is kept to what the pages say. No module confirmed to stop a route
  on events.
- **CRB forced march**: from roll20's compendium text via search, not the aonprd primary
  page, which did not load. Wording matches the 3.5 SRD.
