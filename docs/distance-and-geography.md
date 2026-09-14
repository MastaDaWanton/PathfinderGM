# Distance and geography

Research first, then the plan it produced. It was asked for in as many words on 2026-09-14:

> "we are not currently using distance because i had not yet coded for it however distance
> is a part of pathfinder and it matters for travel and geography. don't code anything yet,
> but do the research on how we can implement actual distance in our application. I have
> begun building maps in world bible but as of right now they use the near/far format, once
> you have finished researching I will need to build both so they can communicate properly."

Two programs have to end up agreeing, so this covers both sides of the file between them.

A second request arrived after the first draft and widened it — *"rooms in a house or in a
space do need a ruler because if combat happens inside then the layout of the house is
important also verticality, i believe, is something we have completely glossed over… every
where needs to be measurable."* That is §6, and it also corrected a conclusion in §5, which
now says so where it stood.

The sweep behind it followed CLAUDE.md's standing instruction — four parallel tradition
searches and a critic pass over their findings. Sources are cited inline, and where a claim
could not be sourced it says so.

The critic pass earned its place: it refuted one claim outright, narrowed the Fate precedent
this project's own design documents rest on, and caught an overstatement about HPA\*. Each
correction is written into the text where the claim appears rather than applied quietly,
because on this subject the *narrowed* versions are more useful than the headlines were. One
of the four researchers also refuted a premise in its own brief, which is recorded in §3.

---

## The plan, and where it has got to

Agreed 2026-09-14. §5 is the reasoning for stages 6–7, §6 for stages 1–5.

| | stage | state |
|---|---|---|
| 1 | Say what is not delivered: a `not_yet` on every movement evolution | **done** |
| 2 | A creature is a box — vertical extent on `SPACE_AND_REACH`, `volume()`, 3D distance | **done** |
| 3 | Elevation on actors; the engine reads movement modes; **the stage-1 caveats come off** | **done** |
| 3b | The situational-modifier pipeline — flanking, higher ground, cover | **done** |
| 4 | The floor under the fight — height per square, and a plan derived from the place id | **done** |
| 5 | Storeys as places, joined by stairs | next |
| 6 | Lengths on the trade edges; a journey costs time | |
| 7 | The map view — level selector, then an axonometric toggle | |

Stage 2 settled one thing the rules do not: **there is no vertical distance rule in PF1e**,
so `grid.distance` now carries a house rule in its docstring — a step is diagonal if it
moves on more than one axis, and the count of diagonals is the second-largest delta. It
reduces to the old two-dimensional answer exactly, which is why it replaced the old body
rather than sitting beside it.

Stage 3 found two things it was not looking for. **Every imported creature walked at 30
feet** — `speed` had been stripped from the stat block beside `speed_note`, so 3,272 of the
7,136 moved at a speed their own block contradicts. And **a body overhead blocked the floor
beneath it**, because `occupied` collected footprints with no notion of height.

It also left a mark on what a guard is worth. The stage-1 test was written to fail the day
the engine learned to fly; the engine learned, and the test passed, because it watched for
the words "elevation" and "fly_speed" and the code said `can_move_vertically`. It asks about
behaviour now.

**Stage 3b built the pipeline stage 3 said it needed.** There was no route by which a
*position* became an *attack modifier*: `grid.flanking` had been written, tested and never
called by anything outside its own tests, and the word "cover" appeared nowhere in
`rules/engine.py`. `rules/position.py` is that route — flanking, higher ground and cover
arriving as ordinary `Modifier`s the way `compulsion.penalty_against` already does, because
all three depend on where *both* creatures are and the sheet knows only its own body.

Still outstanding from stage 3's list: the Fly skill's DCs, and a climber's loss of Dex to
AC — the second of which has no reachable state yet, because a creature without a climb
speed is refused the wall in the first place. Climb checks are what would create it.

Stage 4 gave a place a shape — `rules/floorplan.py`, keyed off the spot where the spot is
one this app generates and off the terrain otherwise, and derived from the place id so the
market has the same stalls for ever without a byte in the save. It found three things: the
battlefield layout stood people inside the new walls, because its arithmetic was written
against an empty field; the save carried neither the heightmap nor the ceiling, so a
campaign put down mid-fight came back with a flier's air unlimited; and the generator's own
scatter was a stripe, because it drew from the **low** bits of a linear congruential
sequence and those cycle with a period of eight.

Stage 1 is deliberately the smallest thing that stops the game claiming something untrue,
and it is independent of every stage after it. The guard that holds it —
`tests/test_movement_modes.py` — is written to **fail at stage 3**, so the apology cannot
outlive the defect it apologises for.

---

## 1. What is true today, measured

### Pathfinder GM has exactly one distance, and it is tactical

`rules/grid.py` is real and complete: integer `(col, row)` squares of five feet, 1e's
5-10-5 diagonal counting, footprints by size, reach, corner-to-corner line of sight, and
weighted A* movement cost. Distances are returned in **feet**, because "every rule in the
book is written in feet and converting at the edges is where sign errors live."

Above that square there is no distance at all. Four measurements:

- **`scene.location_id` is assigned once and never reassigned.** It is set in
  `play/campaign.py:432` at campaign creation, and nothing in `rules/engine.py` writes it
  again. Pangrella ships **12 settlements and 5 travel edges; the game can reach one of
  them.** Distance is not merely missing from travel — inter-settlement travel does not
  exist to put it on.
- **Travel costs no time.** `_op_travel` changes the ground and spot underfoot and never
  calls `advance()`. Walking from the market out to the forest is free on a clock that
  meters thirst, hunger and sleep in hours.
- **The place graph is a clique.** `places._build` gives every place
  `exits=tuple(x for x in all_ids if x != pid)` — everything adjacent to everything, so
  there is no path length even in hops.
- **One time cost is attached to movement anywhere in the app**, and it is a constant:
  `places.VENTURES[kind]["hours"]`, which takes exactly two values — `0` for the sewers,
  cellars, rooftops and alleys inside the walls, `2` for the cave, mine and ruins outside
  them.

### The clock, by contrast, is built and load-bearing

`Scene.advance(minutes, rounds)` is "the one door": it moves `clock_minutes`, expires timed
effects, ticks pools, and advances every body's hunger, thirst and wakefulness counters —
for everybody the campaign holds, not just the party. It deliberately does **not** re-fire
per-round events, and it deliberately does **not** roll the survival checks, because
`survival.pass_hours` rolls dice and can knock a character down.

`_op_venture` already shows the exact shape a journey would use:

```python
toll = survival.pass_hours(actor, hours, self.dice, biome=head.terrain)
self.scene.advance(max(1, toll.hours) * survival.MINUTES_PER_HOUR, charge_body=False)
```

**The receiver for travel time is therefore already written, wired and proven.** What is
missing is only the number of hours — and today that number is a hand-authored `2`.

### World Bible's map coordinates are not geography

`agent_engine/world_map.py` says it plainly: no world contains a coordinate, so a map
"cannot be READ out of a world. It can only be derived from what the world does record,"
which is containment (`parent_id`) and trade edges. It lays the world out as concentric
rings — world at the centre, continents around it, nations around those, settlements around
those — with ring radius computed from how much clearance the children need.

**Ring radius encodes depth in the containment tree. It is not distance.** The module's own
words: "a layout is a claim about *structure*, not about latitude, and the page says so."
Two settlements adjacent on a ring may be a continent apart in the fiction.

So the x/y already on screen must never be read as geography. Doing so would produce
confident, precise, wrong numbers — the worst failure shape available here, because nothing
downstream would look wrong.

The town map editor is the other half, and it is deliberate too: *"Adjacency only: there is
nowhere on this page to type a distance, and the save refuses one if it reaches the prose."*

The hinge is a sentence in `core_world/views_map.py` describing work that does not exist
yet: *"An author who wants a place somewhere in particular will be able to drag it there,
and that position will be the world's, not this layout's."* That unbuilt drag-and-persist
step is where real geography would enter World Bible.

### The contract says no, twice, on purpose

- `docs/campaign-format.md`: **"No maps or coordinates.** Places relate through containment
  (`parent_id`) and trade (`travel`), not geometry."
- `docs/for-world-bible.md`, on the places ask: **"Do not ship distances or weighted
  borders."**
- `docs/places-plan.md` refuses **"weighted edges or traversal cost"** and **"a coordinate
  grid for outdoor space… a second would be a fifth spatial authority."**

Both refusals were made at **room scale**, about the place graph inside a town. Whether they
bind the **overland** scale is the question this document exists to answer, and §4 argues
they do not — but the reasoning behind them turns out to be sound and worth keeping exactly
where it was aimed.

Two further facts that constrain any answer:

- **The export contains no physical quantity at all.** Walking every number in the shipped
  fixture: `chronology[].year`, `play.timeline[].year`, and `world.counts.*`. That is the
  complete list. A distance would be the first.
- **The schema check is major-only.** `world/loader.py` reads `schema_version`, takes the
  major component, and refuses a major it was not written for. A `1.1` export therefore
  loads on a build that only knows `1.0`, and unknown fields are ignored. **Neither program
  blocks the other**: World Bible can ship geography before the app reads it, or after.

---

## 2. What the rules actually need

Pathfinder 1e's overland movement is a product of four inputs. Three of them are tables the
app can own; the fourth is a fact about the world that only World Bible can know.

Base speed against time, from Table: Movement and Distance (verified across
[Archives of Nethys](https://aonprd.com/Rules.aspx?ID=50) and
[d20pfsrd](https://www.d20pfsrd.com/gamemastering/exploration-movement/), which agree
verbatim):

| Base speed | per hour, walking | per day, walking |
|---|---|---|
| 15 ft | 1½ miles | 12 miles |
| 20 ft | 2 miles | 16 miles |
| 30 ft | 3 miles | 24 miles |
| 40 ft | 4 miles | 32 miles |

Terrain and path quality multiply it (Table: Terrain and Overland Movement,
[AoN](https://aonprd.com/Rules.aspx?ID=122)) — ×1 to ×¾ on a road, down to ×¼ for trackless
jungle. A normal day is **8 hours of walking**; each hour past that is a Constitution check
at **DC 10 + 2 per extra hour**, failure dealing 1d6 nonlethal and fatiguing. Survival is
checked **once per hour** against a terrain-keyed DC to avoid getting lost.

Against those four inputs, here is what the two programs hold today:

| input | source today |
|---|---|
| base speed | **present** — actors carry `speed`; the table's left column already exists |
| terrain | **partial** — 9 of the app's 14 biomes map to a PF1e row. `coast`, `urban`, `ruins`, `underground` and `planar` have none; PF1e's `moor` has no biome |
| path quality (highway / road-or-trail / trackless) | **absent on both sides** — the words do not appear in `rules/` or in the export |
| length of the journey | **absent on both sides** — `travel[]` edges carry `carrying` and `friction`, both prose |

Two of four have no source data. That is the ask, and it is small.

The terrain column's partial coverage has a pattern already in the codebase: `races.price_tag`
returns `(cost, words, "exact" | "derived" | "unknown")` rather than silently charging zero
for a tag it has never seen. A terrain word with no PF1e row wants the same three-way answer,
not a default multiplier that quietly makes swamps as fast as plains.

Distance is also load-bearing well below travel, which is the argument for one honest number
rather than a travel-only fudge: Perception takes **+1 DC per 10 feet**; spell ranges are
`25 + 5/2 levels`, `100 + 10/level`, `400 + 40/level`; ranged weapons take −2 per range
increment and simply cannot reach past 10 increments; low obstacles grant cover only within
30 feet. The tactical grid already serves all of these correctly. Nothing proposed here
should touch it.

---

## 3. What the traditions did, and what they abandoned

### The distinction that organises everything: a ruler or a box

The single most useful finding in the sweep. Steamtunnel wrote
[In Praise of the Six-Mile Hex](https://steamtunnel.blogspot.com/2009/12/in-praise-of-6-mile-hex.html)
(2009), the canonical sight-line argument for that hex size — a person on flat ground sees
about three miles, so a party crossing a six-mile hex cannot see out of it. Nine years later
the same author reversed it in
[The Ergonomic 3-Mile Hex](http://steamtunnel.blogspot.com/2018/09/the-ergonomic-3-mile-hex.html),
and the reason is the point:

> a hex can be **a measuring ruler** (fractional distances within it) or **a discrete box**
> (one hex = one turn, entered and exited whole) — and the six-mile hex, once sub-hexes
> were added, was trying to be both. "When you add the sub-hexes, you have stopped using the
> handy distances of the 6-mile hex and actually switched to a discrete model."

Correction worth recording: the sight-line argument is **not** Welsh Piper's, which is where
it is usually attributed. Erin Smale's
[hex-based campaign design](https://welshpiper.com/hex-based-campaign-design-part-1/) series
uses a **5-mile** hex and argues from gazetteer scope and nesting convenience, not sight
lines. My own research prompt asserted the attribution and the sweep refuted it.

Applied here, the ruler/box distinction sorts the whole problem:

- The tactical grid is a **ruler**. Feet, measured, already correct.
- The place graph inside a town is a set of **boxes**. You are at the market or you are not;
  no fraction of the way there exists or should.
- The overland layer is the only place the choice is live.

### Edge cost is how software has always done distance without coordinates

This is near-unanimous across the digital traditions, and it is the closest prior art to
what this app already has.

- **DikuMUD and its descendants** put a movement-point cost on the *sector type of the room
  being entered* — CircleMUD's `movement_loss[]` is `city 1, field 2, forest 3, hills 4,
  mountains 6, underwater 5`
  ([constants.c](https://github.com/Yuffster/CircleMUD/blob/master/src/constants.c)). There
  is no metric distance anywhere; terrain difficulty and distance are one scalar.
- **Civilization** charges movement points per tile entered; roads reduce the cost of the
  edge rather than changing the map's metric.
- **Crusader Kings 3** routes travel *through baronies* and fires events "for every 20
  baronies traveled" ([CK3 wiki](https://ck3.paradoxwikis.com/Travel)) — a hop count, with
  terrain as a percentage speed modifier.
- **Evennia**, the modern MU* engine, states that rooms have "no internal size and no
  inherent spatial relationship to each other," and fakes travel time with a delay on the
  transit command rather than any distance value
  ([Exits](https://www.evennia.com/docs/latest/Components/Exits.html)).

**One counterexample, and it is instructive.** The first pass through this claimed no
strategy game computes travel from measured distance; the critic pass refuted it with
**Aurora 4X**, which times travel *within* a star system as plain distance ÷ ship speed —
50,000,000 km at 3,000 km/s is about 4.6 hours — while travel *between* systems still runs on
discrete jump points ([Aurora wiki](https://aurora4x.fandom.com/wiki/System_Map)).

That is not an exception to the pattern so much as the shape this document ends up
recommending: **measured where space is continuous and the traveller may stop anywhere,
discrete hops where the world genuinely has only a few doors.** Everywhere else surveyed —
Diku, Civilization, CK3, Evennia — the abstraction simply *is* the distance.

The tabletop equivalent is the **pointcrawl**: nodes joined by edges whose cost is travel
time. Chris Kutalik's
[original post](http://hillcantons.blogspot.com/2012/01/crawling-without-hexes-pointcrawl.html)
prices each edge at "about six hours of unencumbered walking," pegged to his encounter-check
interval, and argues for it precisely where terrain constrains the route: "an area maybe
close by how the crow flies but involves a circuitous route by foot." His
[later self-assessment](http://hillcantons.blogspot.com/2016/02/hexcrawls-vs-pointcrawls.html)
narrows the claim rather than defending it — hexes win for open wilderness explored for its
own sake, pointcrawls for deliberate travel between authored places, and a pointcrawl's risk
is becoming "overly linear."

**A trade-route network between settlements is already a pointcrawl.** World Bible's
`travel[]` is the node-and-edge graph; it is missing only the cost on the edge.

### Numeric edge weights: the one case where they were tried and deleted

Both design documents cite this, so the sweep checked it properly. **It holds, with a
correction to what was removed and why.**

**One** earlier edition carried numeric zone borders: the *Dresden Files RPG* (Fate 3.0,
2010) had a **Barrier Rating**, where crossing a border cost shifts equal to its rating — a
closed door a 1, a locked door a 3. The first pass through this attributed the mechanic to
*Spirit of the Century* (Fate 2.0) as well and the critic pass refuted it: SotC resolved an
obstructed move with an Athletics overcome roll justified by aspects, which is the
aspect-based approach Fate Core later **returned to**. Fate Core (2013) removed the rating.
The Fate Core
[Veteran's Guide](https://fate-srd.com/fate-core/veterans-guide) states it directly:
**"Zone borders have been replaced by the use of situation aspects"**, and moving a zone "is
always free if there's nothing in the way."

Both corrections matter for how far the precedent reaches, and both narrow it:

- The borders were not deleted because numbers were the wrong tool for measuring space.
  They were deleted because Fate had a **better general mechanism** — situation aspects —
  that already covered blocks and obstacles, and a bespoke numeric subsystem for one case was
  redundant beside it. The replacement is a *qualitative tag on the obstacle*, which is
  precisely what this project calls a state.
- The numeric weight was **one edition's experiment between two aspect-based ones**, not a
  long-standing feature that collapsed. That is a weaker precedent than "Fate shipped it and
  deleted it" implies, and the honest version is the one worth citing.

That reading makes the existing refusal in `places-plan.md` stronger rather than weaker, and
also narrower: *obstruction between two adjacent places belongs in states and effects, not in
a cost table nobody would tune.* It says nothing about how far apart two towns are.

### Where two scales coexist, the ratio is fixed — with one caveat

Caves of Qud nests a world-map tile (a **parasang**) as a **3×3 grid of zones**, each zone an
80×25 playfield. Dwarf Fortress nests a region map tile as **16×16 local tiles**, each local
tile **48×48 tiles** — about 6,100 feet across — and reuses that middle tier directly as the
unit of overland travel in adventure mode rather than inventing a fourth unit. (The tier
names are the wiki's own; the first pass through this swapped "embark" and "local", which is
worth getting right only because the middle tier is the one doing the interesting work.)

The cross-cutting claim drawn from this — that the coarse-to-fine ratio is always a fixed
engine constant, never variable per place — is **directionally right but stated too
strongly**, and is flagged here as an inference across three examples rather than a law. The
critic pass searched deliberately for a counterexample among roguelikes, layered strategy
maps and procedural nested-scale engines and found none, which is worth something and is not
proof. The solid version: in all three the ratio is *uniform*, and none lets an author vary
how "big" one coarse cell is in fine cells — and that uniformity is what keeps a coarse step
and a fine step from disagreeing.

**HPA\*** (Botea, Müller and Schaeffer, 2004) is the mechanical answer to making two levels
agree: partition the fine grid into clusters, place *entrances* on cluster boundaries, and
give each abstract edge a weight that is **a real fine-grid path cost, computed once and
cached**. A query solves the small abstract graph, then refines each abstract edge into real
steps. The coarse path is authoritative over *which regions* are crossed; the fine path only
fills in the interior.

The paper qualifies itself, and the critic pass held the first draft of this section to it.
Botea et al. say the abstract edge weight "is the length of the shortest path between the two
clusters in the original graph" — so the caching claim is exactly right — but also that paths
"are guaranteed to be optimal with respect to the abstract graph, but may not be optimal with
respect to the original graph," which is why the title says *Near Optimal*.

So "the layers cannot disagree" is false, and the precise version is the one that transfers:
**a single coarse edge weight measured from the fine layer cannot drift from it, because it
was measured rather than authored beside it — but a route assembled from several such edges
is only near-optimal, because it is pinned to fixed entrances.** For a road network that is
not a defect; a real road between two towns does not take the crow's path either.

### The failure mode to design against is identity, not arithmetic

The one documented case of bolting coordinates onto an existing room graph is a tbaMUD
wilderness thread, and it did not break on geometry:

> "You are at (233, 74), standing alone in the grasslands and you log out… Suddenly, you are
> at [34, 65] in the middle of a pack of aggressive wolves!"

([tbaMUD forums](https://www.tbamud.com/forums/4-development/3601-virtual-wilderness-room-pools-and-coordinate-confusion))

Rooms were pooled and recycled by vnum, so a saved position resolved to a different place
later. The accepted fix was **not** to unify the two systems but to declare which layer owns
which kind of location: generated wilderness saves coordinates, authored rooms save the
discrete key.

This is the live risk for this codebase. Place ids are `{location}~{ground}:{spot}` and
campaign saves key off them. Any design that makes `location_id` mutable — which
inter-settlement travel must — has to keep that id meaning one thing forever.

### Units: declare, or fix one and convert at the edge

Both conventions are real and documented.

**Self-declaring** is what the VTTs do. A Foundry scene carries `grid.size` (pixels),
`grid.distance` (units per square) and `grid.units` (a free string like `"ft"`), and computes
everything from those
([GridData](https://foundryvtt.com/api/v12/interfaces/foundry.types.GridData.html)). Its
`CONST.GRID_DIAGONALS` enum even has `ALTERNATING_1`, which is 1e's 5-10-5 rule exactly.
Roll20 does the same per page. Azgaar's Fantasy Map Generator lets the author pick a unit and
a miles-per-pixel ratio.

**Fixing one canonical unit** is what GeoJSON did, after trying the other way. RFC 7946 §4
mandates WGS 84 and nothing else, and Appendix B.1 records the removal verbatim:
**"Specification of coordinate reference systems has been removed, i.e., the 'crs' member of
[GJ2008] is no longer used."** The stated reason is directly on point — alternative
coordinate systems "proven to have interoperability issues," because "GeoJSON processing
software is not expected to have access to coordinate reference system databases"
([RFC 7946](https://datatracker.ietf.org/doc/html/rfc7946)).

That is a per-file self-description tried at internet scale, found to produce readers that
silently mishandled files, and deleted in favour of one fixed system. For a format with
exactly two implementations and one author, the same logic applies with more force: a `units`
string is a second thing to get wrong, and the only honest reason to have one is if the two
programs genuinely disagree about units, which they do not.

The cost of getting this wrong is the standing example: the Mars Climate Orbiter was lost
because ground software produced pound-force-seconds where the navigation software specified
newton-seconds
([NASA](https://science.ksc.nasa.gov/mars/msp98/news/mco991110.html)). The board's wider
finding is the one that matters here — the failure was the absence of **end-to-end
verification at the boundary**, not the units themselves. A declared unit is worth only as
much as the validator that checks it.

Worth noting what the neighbours do: Watabou's generators export GeoJSON in abstract "world
units" with no real scale attached, and Wonderdraft and Inkarnate export images only. **No
coordinates is the default posture of this whole tool category**, not an oversight peculiar
to World Bible.

---

## 4. The options, and what each costs

### A. Coordinates on settlements — `(x, y)` in miles

Every settlement gets a position; distance is computed.

*For:* one number answers every question — distance, bearing, what lies between, whether a
route is plausible. Matches the drag-to-place feature World Bible already intends.

*Against:* it is the **fifth spatial authority** `places-plan.md` warned about, and it can
disagree with the containment tree that is currently the world's only spatial truth (a city
whose coordinates land it outside its own nation). It demands an answer to the projection
question — planar distance diverges badly from geodesic over large spans, by nearly 2× on
ArcGIS's own Reykjavik-Moscow example. And it forces geography to exist for **every**
settlement before **any** travel works, because a coordinate is not optional the way an edge
is.

### B. Lengths on the trade edges that already exist — a pointcrawl

`travel[]` gains a length and a path quality per edge.

*For:* the graph already exists on both sides, and both programs already agree on it. It is
additive, partial by nature — an edge without a length is simply an edge you cannot yet time,
not a hole in a coordinate system. It matches how the fiction actually moves (roads and
passes, not crow-flight). It fits the receiver the app already has: an edge cost in hours is
what `VENTURES` is, with more values. And it is what every digital tradition surveyed
actually does.

*Against:* no bearings, no "what is between", no crow-flight distance, and it cannot answer
"how far is that mountain" — only "how long to that town". A sparse graph can imply absurd
geography (A→B→C much shorter than a direct A→C that has no edge). Kutalik's own warning
about linearity applies.

### C. A hex grid over the world

*For:* the deepest tabletop tradition; distance, containment and content-keying in one
structure; Red Blob Games' axial coordinates make the maths trivial.

*Against:* it is option A with extra steps — the same fifth authority, plus a hex size to
argue about, plus the sub-hex trap Steamtunnel documented. World Bible has no hex anything,
and its map is a containment diagram, not a plane.

### D. Keep it abstract — a time band per edge, no distance

Edges carry `"half a day"`, `"two days"`.

*For:* honest; nothing to contradict; no unit problem at all; closest to what FFG did
deliberately with unnumbered range bands.

*Against:* it puts a **rules number in World Bible's mouth**, because a day's travel depends
on speed, terrain and encumbrance — all Pathfinder's business. It breaks the boundary the
contract is built on far worse than a mile does. And fans re-derived numbers for FFG's bands
anyway, which is what happens when the number is needed and withheld.

---

## 5. What the evidence recommends

**Option B, with distance kept as a derived view rather than a stored second authority.**

The clearest statement of the shape is the counterexample the critic pass turned up. Aurora
4X measures travel where space is continuous and a ship may stop anywhere, and hops where the
world has only a few doors — and it does both at once without either lying about the other.
This app is the same animal: a five-foot grid where a character may stand anywhere, a road
network where a party may not. **Measure inside the ruler, count hops between the boxes.**

The rest of the reasoning, in the project's own terms:

**One vocabulary.** One unit, everywhere, and it is the **integer mile** in the export and
the **integer foot** in the engine, with no `units` string on either — GeoJSON's abandoned
`crs` is the precedent, and two implementations with one author do not need per-file
self-description. A validator at the boundary, because Mars Climate Orbiter's real finding
was the missing end-to-end check.

**One applicator.** A journey's output is **time**, and time already has exactly one door.
Miles never reach the rest of the app: `_op_travel` converts miles to hours through the
PF1e tables and then calls `survival.pass_hours` and `scene.advance`, which is the pattern
`_op_venture` already proves. Nothing else learns what a mile is.

**Severed tells.** The narrator is told "most of a day on the road, and the light is going",
never "42 miles". This is the existing rule about numbers, unchanged.

**Derived, not stored — the `zone_between` pattern, one scale up.** `grid.zone_between`
already answers `engaged`/`near`/`far` from measured feet, so a scene with a map and a scene
without both speak one vocabulary and the intent protocol never learned coordinates. That is
the same move: near/far stays the *view*, distance becomes the *measurement underneath it
where one exists*, and nothing that works today has to change. Cypher's bands are defined as
distance brackets for the same reason; FFG's are not, and its players invented conversions
anyway.

**Miles are a world fact, not a rules number.** This is the one place the contract needs an
explicit amendment rather than an interpretation. `for-world-bible.md` rule 1 says "Do not
write numbers into the `play` layer," and every example it gives is a *rules* quantity —
sizes as modifiers, speeds in feet, clocks in rounds, prices, DCs, rarity percentages. A
distance between two towns is the same kind of fact as a settlement's `scale` or its terrain:
true regardless of which game reads it, expressible without a word of Pathfinder vocabulary.
Rule 2 — no Pathfinder vocabulary in World Bible — stays untouched, because every conversion
from miles to hours to Constitution checks happens on this side of the file.

**And the existing refusals stay exactly where they were aimed.** Fate's deleted barrier
ratings are a real precedent and they argue against weights *between adjacent places inside a
scene* — where the better mechanism is a situation aspect, which this project calls a state.
The town maps already built in World Bible should stay adjacency-only: **which** room you are
in is a discrete fact, and how far the market is from the gate in feet is not a number the
world file needs to carry.

**What is inside a room is a different question, and §6 answers it the other way.** The first
draft of this document said "a room is a box, and it doesn't become a ruler because the road
outside it did." That is right about the place graph and wrong about the floor, and the
correction came from the person who asked for the research:

> "rooms in a house or in a space do need a ruler because if combat happens inside then the
> layout of the house is important also verticality, i believe, is something we have
> completely glossed over… every where needs to be measurable."

Both halves check out on inspection, and the second is worse than "glossed over". §6.

### The shape this points at

A sketch, not a schema — the schema is the next conversation, and World Bible should propose
it the way it proposed the places one.

On World Bible's side, additive to `travel[]`, every field optional:

- **`miles`** — integer, crow-flight or road, whichever the author means, stated once in the
  contract and never per-record.
- **`road`** — one of `highway`, `road`, `trail`, `none`, which is the column PF1e's table
  needs and neither program has.
- **`crosses`** — the terrain words the route passes through, in World Bible's own
  vocabulary, mapped on this side with `exact`/`derived`/`unknown` honesty rather than a
  silent default.

On Pathfinder GM's side, nothing about the grid changes. What would be new is a journey op
that makes `location_id` mutable, prices the trip through the 1e tables into hours, and
spends those hours through the door that already exists.

### What to refuse, with the reason

- **Reading `world_map.py`'s ring coordinates as geography.** They encode tree depth. This is
  the single most tempting mistake available, because the numbers are already there and
  already look like positions.
- **A `units` string.** One canonical unit, fixed in the contract.
- **Weights inside a town.** Fate deleted them; obstruction is a state.
- **Floats.** Integers in a base unit; the drift argument is standard, and this codebase
  already returns feet as integers for the same reason.
- **A default length for an edge that has none.** `price_tag`'s three-way answer, not a
  guess. An unknown journey is unknown.
- **A second spatial authority.** If distance is stored anywhere but on the edges of the one
  graph that already exists, the four-authorities failure that `places.py` was written to end
  comes back one scale up.

### Risks worth naming before anything is built

- **Identity.** Making `location_id` mutable is the tbaMUD lesson waiting to happen: campaign
  saves key off place ids of the form `{location}~{ground}:{spot}`. Which layer owns a
  position has to be settled before a save is written, not after.
- **Time makes the world move.** Travel currently costs nothing, so nothing else does either.
  The moment a journey costs three days, `advance()` expires effects and moves every body's
  counters — and `pass_hours` rolls the checks that `advance()` deliberately does not. A
  three-day march that moves hunger counters without ever rolling against them would be the
  survival module's own named failure — "the clock moved and the body did not know" —
  arriving by a new route.
- **Sparse graphs imply false geography.** Five edges over twelve settlements means most pairs
  have no route at all. "You cannot get there from here" is an acceptable answer; a silently
  invented one is not.
- **The middle scale stays empty.** PF1e has tactical, local and overland. This proposal
  fills tactical (already done) and overland, and leaves local — a town's own hundreds of
  yards — as boxes. That is a deliberate gap, and Ultima VI is the reminder that collapsing
  scales is also a legitimate answer someone eventually chose.

---

## 6. Verticality, and what is inside a room

Added after the first draft, on the objection that rooms need a ruler because fights happen
in them, and that verticality had been missed entirely. Both are correct. The second is not a
gap — it is a feature the forge describes, prices and cannot deliver.

### What is there today, measured

- **The grid has no third dimension.** `Point = tuple[int, int]`. `Grid.height` is a naming
  trap: it is the number of rows, not an elevation.
- **`rules/engine.py` contains zero occurrences** of flying, elevation, higher ground or
  airborne.
- **A race can take Flight, and everything about it works except the flying.** Built through
  the real path — `derive`, which calls `expand` — a Medium race with the `flight` and `climb`
  evolutions comes out as:

  ```
  tags     ['race.x', 'move.fly.30', 'move.climb.30']   .base resolved against its own speed
  speeds() {'land': 30, 'fly': 30, 'climb': 30}          on the sheet, correctly
  price    (4, 'fly 30 ft (clumsy)', 'exact')            priced from the ARG anchor
  not_yet  []                                            ← the defect
  ```

  Two first-draft claims here were wrong and are corrected rather than quietly dropped. The
  evolutions do **not** cost race points — the catalogue's own preamble says `points` is "the
  summoner's own cost, kept for the record; a race pays nothing for an evolution", and the
  bench footer says "evolutions cost none". And the fly speed **does** reach the sheet: the
  first measurement called `speeds()` on a hand-written document and so skipped `expand()`,
  which is the step that turns `move.fly.base` into `move.fly.30`. That was a bad measurement,
  not a bug.

  What is real: **nothing in the engine reads a movement mode at all.** `races.speeds()` has
  three call sites — two in `races.py`, one in `sheet.py` — and all three only describe. Grep
  `rules/engine.py` for flying, elevation, higher ground or airborne and there are no hits,
  because `Point` is two-dimensional and a fly speed has nowhere to go.

  So this is the natural-attack defect's quieter cousin. A bite was *refused* when declared;
  a fly speed is simply never asked about. And where the attack evolutions admitted it — 21 of
  54 carry a `not_yet` — the movement ones said nothing, while the **world-derived path for
  the very same tag has always said it**: `races.CUES` grants `move.fly.30` alongside the
  sentence *"a fly speed: the engine moves on the ground only"*. Two doors to one tag,
  disagreeing about what it delivers. **Closed 2026-09-14**: the four movement evolutions now
  carry their own `not_yet`, and `tests/test_movement_modes.py` pins both halves — the caveat
  must exist, and it must come off the day the engine learns the word.
- **Monsters' climb speeds are prose.** The bestiary carries
  `speed_note: "40 ft., climb 20 ft."`, a string. `speed_note` appears once in the codebase,
  in a field allowlist in `bestiary.py:303`. Nothing parses it. A phase spider's climb speed
  is decoration.
- **Every fight happens on the same empty field.** `begin_encounter` lays a bare `Grid()` —
  20×20 squares of open floor — and `end_encounter` throws it away again, deliberately:
  *"The battlefield goes with the fight."* The only code that ever writes a `blocked` square
  is `engine.py:630`, where a **spell** creates terrain. So the only walls that have ever
  existed in this game were conjured. **A fight in a cellar has the same geometry as a fight
  in a meadow.**

That last point is the important one, and it is worse than "rooms have no ruler". The place
graph knows the party is in the cellar. The grid the fight runs on has never heard of it.

### What Pathfinder actually says about the vertical — very little

This was checked expecting the rules to be thinner than people assume, and they are thinner
than that. The researcher fetched the pages rather than trusting summaries.

**There is no rule for measuring distance in three dimensions.** Both
[Movement, Position, and Distance](https://aonprd.com/Rules.aspx?ID=173) and
[Measuring Distance](https://aonprd.com/Rules.aspx?ID=175) define the 5-foot square and the
5-10-5 diagonal and **contain no vertical clause at all**. Whether the diagonal rule applies
going up is not answered anywhere. A Paizo rules thread on monster height and reach settles
on treating a creature's space as a cube, and closes with no developer ever having resolved
it.

Four more things are simply absent from the rules, confirmed as absent rather than unfound:
how high "higher ground" has to be; whether a Medium character can reach something clinging
20 feet up; what happens to a flier that is knocked unconscious; and what damage a creature
takes when another lands on it (only *objects* falling on creatures has a rule).

What the rules **do** give:

| rule | value | source |
|---|---|---|
| Higher ground | **+1 melee, +0 ranged** | Table 8-5, [Combat Modifiers](https://www.aonprd.com/Rules.aspx?ID=180) |
| Fly: hover | DC 15 | [Fly](https://legacy.aonprd.com/coreRulebook/skills/fly.html) |
| Fly: turn >45° / 180° | DC 15 / DC 20 | same |
| Fly: ascend steeper than 45° | DC 20 | same |
| Manoeuvrability | clumsy −8 … perfect +8, **on the check only** | same |
| Climb speed | ¼ speed, or ½ at −5 | [Climb](https://aonprd.com/Rules.aspx?ID=1757) |
| Failing a Climb check by 5+ | you fall | same |
| Falling | 1d6 per 10 ft, max 20d6 | [Falling](https://aonprd.com/Rules.aspx?ID=328) |

**The spider answer is a rule, and it is a good one.** A creature with a climb speed gets a
+8 racial bonus, may **always take 10 even when threatened**, and — the part that matters —
**keeps its Dexterity bonus to AC while climbing, and attackers get no special bonus against
it.** A normal climber loses Dex to AC and cannot use a shield. So the rules already say that
a thing which climbs for a living is dangerous on a wall and a person who climbs is
vulnerable on one. A giant spider has climb 30 ft. and Climb +16. None of that can express
itself on a 2D grid.

**Fireball is genuinely a sphere.** [Aiming a Spell](https://www.aonprd.com/Rules.aspx?ID=228)
defines a spread as extending "in all directions" and able to turn corners; a cylinder's
vertical extent is explicit. So area effects are already three-dimensional in the rules and
two-dimensional in this engine — which is a correctness gap today, not only a missing feature.

**And the tradition's direction of travel is one-way.** 3.5 gave manoeuvrability hard gates —
minimum forward speed, turn radius, grades that could not hover. Pathfinder 1e kept the five
names and the numbers and **threw the gates away**, replacing "can this creature attempt it"
with "roll against a DC". Pathfinder 2e dropped manoeuvrability altogether and made flight a
speed, with hard manoeuvres gated by Acrobatics proficiency. Every edition that tried
geometric flight constraints walked them back. *No sourced designer statement explains why* —
that pattern is read off the rules changes themselves, and is flagged as inference.

**The design consequence is the honest one: PF1e does not tell us how to measure the vertical,
so anything built here is a house rule filling a vacuum.** It should be written down as one.

### What software did, and who retreated

- **Nobody who does tactical-grid combat well uses voxels.** X-COM (1994) had genuine
  multi-storey battlescapes; Firaxis's 2012 reboot cut to a couple of levels and a fixed
  camera with 90° rotation, chosen specifically against disorientation. The team's own
  postmortem records cutting visualised sightlines after months because the lines were
  *"tough for the player to determine what was going on."* **Caveat, and it matters:** no
  developer quote says "we cut multi-floor because X" — that causal link is the researcher's
  inference and is flagged as such. Julian Gollop went back toward full verticality in
  Phoenix Point when free to.
- **Cataclysm: DDA's lesson is about optionality, not verticality.** Z-levels were a toggle
  for years; the [PR that removed the option](https://github.com/CleverRaven/Cataclysm-DDA/pull/41707)
  made them mandatory because supporting both modes left "complicated map code, with lots of
  subtle and weird bugs that show up depending whether z-levels are on or off." If this is
  built, it should not be optional.
- **Every navmesh is 2.5D plus link edges.** Unity's off-mesh links, Unreal's bounds volumes,
  Recast/Detour's layers-joined-by-off-mesh-connections. Volumetric octree pathing exists
  only as a bolt-on for freely flying agents.
- **Final Fantasy Tactics is the closest precedent to what is wanted here**: the logic grid
  stores **a height per tile**, and a unit's `Jump` stat says how large a height difference it
  can cross. That single scalar buys rooftops, cliffs, "you cannot get up there", and
  area-effect reachability — at the cost that nothing can ever be *underneath* a walkable
  tile in the same column.
- **Foundry VTT is the precedent for the other half**: tokens carry an `elevation` number, and
  the core ruler measures **true 3D Euclidean distance** between waypoints at different
  elevations. Core deliberately gives *walls* no height — the
  [feature request](https://github.com/foundryvtt/foundryvtt/issues/1829) was closed as "not
  planned" — which is why the Wall Height and Levels modules exist.
- **Roll20 is the cautionary one, and it is this codebase's current bug exactly.** Roll20 has
  no elevation concept; people fake it with a number on the token, and the complaint in its
  own forums is that the number "is not counted in the distance measures". An elevation that
  looks right on the sheet and never reaches the maths is precisely what `move.fly.base` is
  today.
- **Multi-floor buildings are stacked flat maps joined at stairs** everywhere it works —
  Foundry's Levels, Caves of Qud's strata, Dwarf Fortress's z-levels — not one continuous
  volume.
- **Interiors can be generated.** Watabou's [Dwellings](https://watabou.github.io/dwelling.html)
  produces multi-storey floor plans with rooms assigned real purposes and floors joined by
  stairs. The academic line (treemap partition plus a room-adjacency graph with constraints)
  is single-floor and not seed-deterministic.

### What this points at

Three pieces, each with precedent, and none of them a voxel.

**1. A height per square, on the Grid.** One integer, default 0 — the FFT heightmap. This is
what makes a room's layout real: a table to fight across, a gallery above the hall, a
cellar's low ceiling. It costs one number per non-zero square in a structure that already
stores terrain as sparse sets precisely because "a battlefield is mostly ordinary floor".

**2. An elevation per actor, in feet above its square.** The Foundry scalar. A spider on the
ceiling is at elevation 20; a flier is at whatever it climbed to. This is where `move.fly.*`
and `move.climb.*` finally connect to something, and where the climb-speed package — take 10,
keep Dex to AC, no bonus for attackers — becomes real.

**3. Distance measured in three dimensions, by the same rule as two.** Since the rules are
silent, the choice should be the one that adds no second rule to learn: extend the existing
5-10-5 counting to the third axis, so `distance()` answers one way everywhere and
`zone_between` keeps deriving near/far from it without knowing anything changed. Write the
house rule in the docstring, as this codebase does with everything it invents.

**Floors stay places, not voxels.** A building's storeys are nodes in the place graph joined
by stairs — which the graph already does: `places.mint` has a branch for *"a different ground
under the same roof: the sewers under a town."* Storeys are that, upward. This is the one
decision that keeps the whole thing from becoming a second spatial authority.

**And the floor plan derives from the place id.** `places._seed` is a SHA-256 of the id,
chosen so "the same town would not lay itself out differently after a restart". A place id is
already durable, so `_seed(place.id)` gives the same house every session, forever, for free —
generated on demand, stored nowhere, exactly as the spot list already is. The grid stops being
scenery laid down per fight and becomes **the place's own shape**.

The X-COM retreat is the strongest argument against all of this, and it is worth saying why it
may not bind: its costs were **camera, free-look disorientation and on-screen legibility**, in
a game whose primary interface is a 3D view. This game's primary interface is prose — the
narrator says the spider is on the ceiling — and the map is a secondary panel. The costs that
do bind are Cataclysm's (do not make it optional) and Roll20's (a number that does not reach
the maths is worse than no number).

---

## 7. What could not be sourced

Recorded rather than filled in, per CLAUDE.md.

- No sourced designer statement for **why 5e dropped 3.5's terrain-multiplier table**, or why
  4e mandated squares. The 4e/5e rulebooks are not freely republished and the claims about
  them here rest on secondary summaries.
- **PF1e's encounter-distance figures** were verified verbatim for plains (6d6 × 40 ft);
  the other terrains are aggregated from search rather than individually confirmed, and
  jungle, aquatic and underground were not found at all.
- **No documented case** of a system tracking a measured layer and an abstract layer that
  then drifted apart. The sweep looked for one specifically. Its absence is suggestive and is
  not evidence.
- **Fate's Barrier Rating mechanic itself** is secondary-sourced, from Dresden Files RPG
  rules summaries rather than the book; the *removal* is primary, from the Fate Core SRD.
- **Whether any engine runs two spatial scales at a ratio that varies per place.** Searched
  for deliberately, twice, and not found — which is not the same as established.
- 13th Age's designers refuse measured distance, but **no direct quote explaining why** could
  be found, which is a shame given that both of them designed 4e.
- Azgaar's route export **appears to carry no length field**, but this is a reported absence
  rather than a confirmed one.
- **How to measure distance vertically in PF1e.** Confirmed **absent** from the rules by
  direct inspection of both Measuring Distance pages, not merely unfound. Also absent: how
  high "higher ground" must be, whether a Medium creature can reach a ceiling-clinger, what
  happens to an unconscious flier, and creature-falls-on-creature damage.
- **Why Pathfinder 2e dropped flight manoeuvrability**, and why 3.5's turn-radius rules are
  generally called unplayable. The rules changes are sourced; no designer said why.
- **Why XCOM 2012 cut the original's multi-storey battlescape.** The camera and
  sightline-legibility quotes are real; the causal link to verticality is inference.
