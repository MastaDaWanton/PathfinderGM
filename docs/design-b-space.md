# Design B: between the gate and the road

Phase 0 research and design for Lane B of `docs/fix-plan-2026-09-28.md`: the scale of space
between a settlement's rooms and a journey of days. It is read-only; no code was changed.
Every cause below was measured on the fixtures, the Bobby save, or the code on
`fixes-2026-09-28`.

---

## 1. Items covered

| Item | Cause, measured |
|---|---|
| 16.1, 17.2 | `leave` maps to no op. `interpret.ops_for` handles only `go`. Replay turn 5: reading `leave: outside it`, plan `travel place=the way in` |
| 16.2 | The tell was "The way there ran through the well". `went_by` carries names only |
| 16.5 (and 18) | `_op_travel` charges time only on an urban↔non-urban change (60 min, `engine.py:7208`). In-town hops are free |
| 16.6 | The world has no bearings, and the brief never says so |
| 17.1 | Two scales only: `travel` among a town's rooms, and `journey` between settlements, costing days |
| 17.3 | `places.KINDS` is the settlement table; it has no road or crossroads (replay turns 6 and 7) |
| 17.4, 19 | `prompts.py:926` prints road names only. `legs_from` holds `miles`, `by` and `crosses`. No continent, nation or climate fact reaches the brief. "North to Dustgate" was invented |
| 17.6 | The ROADS OUT sentence was pasted as signposts. The check is Lane A's; this lane reshapes the block |
| 20.1 | `bde94b038cba~forest:the-approach` is under the village's id, and the panel prints `c.location.name` |
| 20.2 | `travel biome=forest` accepted unchecked. Vormoor's roads cross farmland then mountain; Drossakar is ash-fields, badlands and volcanic ridges |
| 20.3 | `floorplan.BY_SPOT["the-approach"].about` is "the way in, and little to hide behind" |
| 20.5 | "The road to Grotburrow" was claimed with no journey |

Four more defects surfaced while reading. None was in the playtest list; all are in this
lane's territory:

- **Every road leg is priced as trackless.** `legs_from` reads `row.get("road")`, which no
  export ships. Both worlds ship `by: "road"`, so `pace()` takes the trackless column.
  Vormoor→Dustgate (72 miles, farmland then mountain) costs 38 hours; the road column gives
  about 27.
- **The warrant check tests only the destination** (`going_to.name in ENTRANCES`). A
  travel whose route passes through the way in to outside ground is never checked there.
- **`biomes.detect` reads "ash-fields" as grassland.** Its regex has no trailing `\b`.
  Vormoor's derived biomes are `desert, grassland, mountain`, and the grassland is this
  artefact.
- **A stopped-short journey stands at `region_set(origin)[0]`**, "the approach", next to
  the town it left, even hours out.

---

## 2. Prior art per tradition

`docs/distance-and-geography.md` (2026-09-14) already surveyed overland distance: the
ruler/box split, Diku sector costs, pointcrawls, HPA\*, and the narrowed Fate precedent. It
concluded "measure inside the ruler, count hops between the boxes". This sweep adds the
middle scale, bearings, and time for short walks.

**Pathfinder 1e.** Table 7-6 has three scales. At speed 30: tactical 30 ft a round, **local
300 ft a minute**, overland 3 mph. Local movement is for "characters exploring an area", in
feet per minute ([AoN, Movement](https://aonprd.com/Rules.aspx?ID=50)). Table 7-8 splits
overland pace into highway, road or trail, and trackless. The app uses the tactical and
overland rows and never the local one. That missing row is 16.5.

**Inform.** Recipe Book §3.4, "Continuous Spaces and The Outdoors"
([RB 3.4](https://ganelson.github.io/inform-website/book/RB_3_4.html)), models the outdoors
as rooms with blurred boundaries:

- **backdrops** hold what can be seen but not reached. Waterworld answers "You are too far
  from [the noun] to do anything but look";
- **regions** carry a backdrop across many rooms
  ([WI 3.9](https://ganelson.github.io/inform-website/book/WI_3_9.html));
- **descriptions adapt** to say which way leads into more of the same ground (Tiny Garden);
- **a signpost** gives distances (Hotel Stechelberg).

The mapping here: the land around a settlement is a region backdrop, described and never
entered. The places outside are a handful of rooms. A bearing is what a signpost says.

**Blue Lacuna** (Aaron Reed) navigates by landmarks, and the compass is an object found in
the game ([Emily Short](https://emshort.blog/2009/01/30/blue-lacuna-ch-1/)). One reviewer
struggled to navigate until they found the compass
([Jay is Games](https://jayisgames.com/review/blue-lacuna.php); a secondary source, and I
could not find the author's own verdict).

**MUDs.**

- Discworld MUD fills the land between cities with "terrains". `walk` moves one room at a
  time; `journey` moves many ([dwwiki, Terrains](https://dwwiki.mooo.com/wiki/Terrains)).
  I saw this only through a search summary: both the wiki and the MUD's own docs refused
  the fetch. It is this app's `travel`/`journey` split, one scale up.
- A CircleMUD builder planned wilderness descriptions "based on the surrounding sectors"
  rather than stored per room
  ([CircleMUD list, 2000](https://www.circlemud.org/maillist/2000-01/0010.html)). Describing
  the land from the world's own words is the shape taken here.

**Hexcrawls and pointcrawls.**

- The Alexandrian counts time in watches, charges ×1 on roads, and makes navigation harder
  off them ([Hexcrawl Part 2](https://thealexandrian.net/wordpress/17320/roleplaying-games/hexcrawl-part-2-wilderness-travel)).
- When players "slip off the pointmap", the GM should "funnel them logically into the
  pointmap" ([Pointcrawls](https://thealexandrian.net/wordpress/48666/roleplaying-games/pointcrawls)).
  That is the job of mapping "I leave the village" onto a real node.
- West Marches makes the town a hard line: safe inside, wild outside
  ([ars ludi](https://arsludi.lamemage.com/index.php/94/west-marches-running-your-own/)).
  "Danger grows with distance from town" appears only in secondary summaries
  ([RPG Museum](https://rpgmuseum.fandom.com/wiki/West_Marches)); I could not confirm it in
  Robbins's own posts.

**Fate.** Fate Core replaced numeric zone borders with situation aspects
([Veteran's Guide](https://fate-srd.com/fate-core/veterans-guide)). The Toolkit's zones page
covers conflicts only ([Toolkit](https://fate-srd.com/fate-system-toolkit/zones), checked).
So Fate says nothing about overland distance.

**CRPGs.**

- **Ultima I–V** kept towns and the overworld on separate maps at separate scales. Ultima VI
  "uses a single scale, with towns … seamlessly integrated"
  ([Wikipedia](https://en.wikipedia.org/wiki/Ultima_VI:_The_False_Prophet)).
- **Daggerfall** fast travel asks for cautious or reckless, foot or ship, inns or camping,
  and quotes days ([UESP](https://en.uesp.net/wiki/Daggerfall:Traveling)).
- **Mount & Blade** leaves a town straight onto the world map. There is no middle scale
  ([StrategyWiki](https://strategywiki.org/wiki/Mount&Blade/Towns)).
- **Pathfinder: Kingmaker**'s global map has locations *and crossroads* as nodes, and travel
  on it spends calendar time
  ([GameFAQs](https://gamefaqs.gamespot.com/pc/242460-pathfinder-kingmaker/faqs/78328/traveling-in-the-overworld-map),
  a secondary source).

**How big a town is.** *Medieval Demographics Made Easy* gives about 38,850 people per
square mile inside walls
([PDF](https://donjon.bin.sh/fantasy/demographics/medieval-demographics-made-easy.pdf)).
Critics call that density high. It is used only for the order of magnitude of a walk.

**Could not be sourced:**

- How much time passes on Kingmaker's local maps.
- Ultima VII's minutes per step.
- Any named "near-town ring" procedure in the OSR literature. The ring below is this lane's
  own design, built from pointcrawl nodes and Inform's region/backdrop split.

---

## 3. Tried and abandoned, and why

1. **Separate scales with a hard cut.** Ultima I–V jumped from overworld to town; Ultima VI
   abandoned that for one scale. This app has the same cut: from the way in, the next step
   is a three-day journey. Without coordinates a continuous scale is impossible, so the cut
   is softened with a small middle ring.
2. **A large generated wilderness.** Daggerfall's generated land between towns is remembered
   as empty. Morrowind first planned the whole province that way, then chose hand-crafted
   objects over "random algorithmic methods". Ken Rolston: "we don't want to jump into this
   and fail" ([Wikipedia](https://en.wikipedia.org/wiki/The_Elder_Scrolls_III:_Morrowind)).
   So: a closed ring of at most six named places, each drawn from what the world wrote.
3. **Weighted borders.** Fate's Barrier Rating was removed because a general mechanism
   already covered obstacles. The minutes here are one uniform PF1e rate over fixed bands
   per tier, never per-edge weights. Caves of Qud and Dwarf Fortress keep their scale ratios
   uniform for the same reason. Tolls and weather stay as meetings or states.
4. **A subsystem for one case.** The Alexandrian dropped his river-crossing mechanic for a
   ×¾ speed. The outskirts likewise get no new mechanic: they reuse `travel`, `ontheway`,
   `found` and `journey`.
5. **Navigating without a compass, and no fallback.** Blue Lacuna kept a findable compass.
   This world has no bearings, so the brief says so and answers in roads. Real bearings
   become a World Bible ask, never an invention.
6. **Coordinates bolted onto rooms.** In tbaMUD, rooms were pooled by number, so a saved
   position came back as a different place. So outside ids keep the settlement id at their
   head, and are derived, never stored.
7. **This repo's own sibling field.** `scene.biome` was stored beside `scene.at`, then
   removed (`test_nothing_writes_the_ground_beside_the_place`). The plan's `Scene.outside`
   would be the same defect under a new name.

---

## 4. Recommended design per item

### The id grammar for outside places

Ids stay `{loc}~{ground}:{spot}`.

- **The ring marker.** `{loc}~{ground}:@{slug}` marks the settlement's **outside ring**.
  `@` cannot come out of `_slug`, which keeps `[a-z0-9 ]` only, and no separator uses it
  (`~`, `:`, `^` and `/` are taken).
- **The slugs** are a closed set: `@the-outskirts`, `@the-fields`, `@the-shore`,
  `@the-crossroads`, `@the-road-to-{to_id}`, and `@along-the-road-to-{to_id}`.
  `{to_id}` is the World Bible id, never the name, because a rename rewrites names.
- **The ground is always a biome word taken from the world** (see 20.2). So `terrain_of`,
  `scene.biome`, `location_of` and floorplans parse exactly as today.

`places.setting_of(place_id) -> "in" | "under" | "outside"` is a pure parse:

1. Head ground `urban` → `in`.
2. Spot root (before the first `/`) starts with `@` or is a `_WILD` slug → `outside`.
3. No `/` at all → `outside`. This covers authored non-urban places and open ground.
4. Otherwise (minted under a town room with different ground), `outside` if the last
   segment is a `VENTURES` label with `hours > 0` (cave, mine, ruins, tower), else `under`
   (sewers, cellar, crypt).

Bobby's `bde94b038cba~forest:the-approach` parses as `outside` with no migration.

**The ratchet.** Add `test_nothing_writes_outside_beside_the_place`
(`_assignments("outside") == []`). The writer allowlists are unchanged: ring places are
entered by `Scene.move`, inside `_op_travel`.

### 17.1: the ring

`rules/outskirts.py: ring(world, location) -> tuple[Place, ...]` is deterministic, built from
`geography.roads_out` and `geography.land_around`.

| Place | Exists when | Ground | Caption (its own) |
|---|---|---|---|
| the outskirts | always, for a settlement | first `near` | "where the last houses give out and the land begins" |
| the road to {To} | each road or river leg | leg `crosses[0]` | "where the road to {To} leaves {Here}" |
| the crossroads | two or more road legs | first `near` | "where the roads out part" |
| the fields | `farmland` in `near` | farmland | "what {Here} grows, and whoever is working it" |
| the shore | coast, or the settlement's own words put it on water | coast | "where the land stops and the water starts" |

**Exits:**

- Each urban place in `ENTRANCES`, except the docks and the bridge, is joined both ways to
  the outskirts.
- The outskirts joins the crossroads (or the single road), the fields and the shore.
- The crossroads joins each road.
- Nothing offers more than six ways on, except a crossroads with six roads (2 of Aurvantis's
  76 settlements). There the sixth road hangs off a second fork.

Road legs per settlement, measured: Aurvantis 0:5, 1:15, 2:14, 3:17, 4:9, 5:2, 6:2;
Pangrella 0:3, 1:6, 2:3.

**Sea legs** leave from a port's docks, which are already in town. From a non-port they
leave from the shore if there is one, else from the outskirts ("the road to the coast, and
then…" is already the tell).

**Wiring into the place set:**

- `Engine.places()` passes the ring through a new `places.for_scene(..., ring=())`.
- `for_scene` adds `region_set` only when `at`'s root is a `_WILD` slug. Today it would
  graft a farmland `_WILD` region onto the fields.
- The road stretch `@along-the-road-to-{to_id}` ("on the road to {To}") joins only while it
  is `at`, as `region_set` joins today. Its ground is the crossing at the fraction walked.
  Progress stays in `Scene.road`, which already exists.

### 16.1 / 17.2: `leave` becomes a move

`interpret.ops_for` changes as follows.

- **`leave`, indoors:** `travel` to the first exit under the sky.
- **`leave`, outdoors in town:** `travel` when the place slot is empty, or names the
  settlement, its scale word, or *town, village, city, outside, out, it*.
- **`go` to a phrase `find` cannot resolve** but that contains *road, path, track,
  crossroads, fields, outskirts* or *out of town*: `travel`.

The destination is held by the sampler; enums are enforced 6 of 6 (memory
`ollama-schema-enforcement`). `interpret.travel_choices(frame, scene, places, location)`
returns the values the plan's `travel.place` enum may take:

- ring names only, for leaving the settlement;
- street exits only, for leaving a building;
- otherwise everything but here, which is today's behaviour.

`_WHAT_EACH_IS` becomes: "leave — walk out of where you are, a building or the settlement
itself, with nowhere else named".

### 16.5 / 18: travel costs minutes

**minutes = feet ÷ (speed × 10 × pace)**. This is PF1e local movement. `pace` is
`journey.pace(ground, "road")[0]` outside and 1 in town.

| Step | Band (feet) | Min at 30 ft | Basis |
|---|---|---|---|
| hop, village | 400 | 2 | MDME: 500 people ≈ 600 ft across, about 1.5 hops |
| hop, town | 1,200 | 4 | 7,000 people ≈ 2,240 ft across, about 2 hops |
| hop, city | 2,400 | 8 | 100,000 people ≈ 8,470 ft across, 3–4 hops |
| ring hop | 2,640 | 9–12 | half a mile; an assumption |
| to open ground (`_WILD`) | 15,840 | 60 | today's hour, now derived |
| open ground, `beyond` | 63,360 | 240 | half a walking day |

- The minutes are summed over the hops actually walked, so a meeting cuts the sum short.
  They are charged once by `Scene.advance(minutes, charge_body=False)` in `_op_travel`.
- Walking back along a stopped road charges the hours already walked, through `_march`,
  before `scene.road` clears. Today it clears for free.
- The tell says the time in words, never a count: `geography.walk_words` ("a few minutes'
  walk", "a quarter of an hour", "the better part of an hour").
- A city crossing is about 30 minutes, so the clock pop-up (60 minutes or more) stays quiet
  in town and fires outside, which is what item 18 describes.

### 16.2: the walk has material

The travel effect gains `went_by_about: [{"name", "about"}]`. `about` is the place's own
line: the world's authored one where it exists ("The water everyone draws from, and the
queue that forms at it."), the table's otherwise.

The tell reads: "The way there ran through the well — the water everyone draws from, and the
queue at it — and then the way in." A move from `in` to `outside` adds one sentence of land
in the world's words: "Past the last house the land opens: farmland, and mountain beyond it."

`gm/checks/route_walked.py` flags a beat where `went_by` is non-empty and the prose names
none of those places by name or head noun. The repair asks for "one clause for each place
passed, in order". There is no backstop; the tell stands on the record.

### 16.6: bearings from the world

**Trigger:** a reading whose `look` or `search` object is a bearing phrase (*bearing,
direction, which way, where … is, road to, signpost, the way to*). The ROADS OUT block then
adds:

> BEARINGS (fact): the world records no compass direction for any of these. Answer with the
> roads, where they leave from, what they cross, and how long.

A question about "a larger place" is answered from each destination's own scale word.

**Check:** `gm/checks/bearing_invented.py` flags a compass word (*north, south, east, west,
north-east…*) within six words of a settlement name or of *road/path to*.

- **Repair:** the road-relative answer.
- **Backstop:** cut the compass phrase ("to the north", "north to").

When an export ships `bearing`, `Road.bearing` is set, the block states it, and the check
allows only that bearing.

### 17.3: road kinds are foundable

`places.OUTSIDE_KINDS` holds five kinds: road, crossroads, milestone, ford, and bridge (on an
outside parent). A ford and a bridge need water. `fits_here(kind, location, parent=None)`:

- an outside kind off an urban parent is refused, with the fix: "A crossroads is out on the
  road, not in the market; go to the outskirts first";
- off an outside parent it is accepted, with the water cue required for ford and bridge;
- settlement kinds are unchanged.

`_op_found` passes the parent.

### 17.4 / 19: roads out and the land around, in the brief

Both blocks are **label-and-fragment** on purpose. Complete sentences get pasted (17.6), and
Lane A's `brief_verbatim` check sees the labels as scaffold.

**`gm/brief/roads_out.py`** runs whenever there are legs, and replaces today's ROADS OUT
line:

```
ROADS OUT OF VORMOOR (fact; the only settlements reachable, each by a journey of days; no compass bearing is recorded — never give one):
  Dustgate — a town; by road, from the outskirts; about three days on foot; farmland, then mountain.
  Scrapden — a town; by road, from the outskirts; about four days on foot; farmland, then mountain.
  Ledgerwarren — a city; by sea, after the road to the coast; about a day aboard.
```

- Days are number words from `journey.hours_for` at the PC's speed. No miles.
- No miles in the world → "how far, nobody has written down".
- No `crosses` → the clause is omitted.

**`gm/brief/land_around.py`** runs when the setting is `outside`, when here is an entrance,
or when the reading has `leave` or a bearing look:

```
THE LAND AROUND VORMOOR (fact; describe from these, in your own words):
  underfoot here: farmland.
  close by: farmland, where the roads start.
  further out: mountain, where every road climbs.
  the wider land, Drossakar: ash-fields, iron-rich badlands, geothermal vents; volcanic ridgelines, black-rock canyons, a few fertile crater basins.
  weather: hot, dry, prone to ashfall storms off the active peaks.
  water: coral and driftwood stilt-housing.
  not here: woodland.        ← only on a turn whose move named absent ground
```

Values are the world's words, unedited. Only the labels are the app's.

**Check:** `gm/checks/land_described.py` finds two defects.

- **(a) No land at all.** An `in`→`outside` beat, or a bearing answer, carries no word from
  the Land lexicon. The lexicon is the world's comma-split words plus the `biomes._LOOKUP`
  phrases of the near and beyond grounds. The repair asks for one physical detail from that
  list; this is the opening's drawn-from-the-place check, the shape that held.
- **(b) Absent ground named.** A biome phrase whose biome the Land lacks, such as "pine" or
  "trees" around Vormoor. The repair names the ground that is there. The backstop cuts the
  sentence.

### 20.1: outside reads as outside

`geography.where(world, scene, here)` gives the panel and the brief one label:

| Setting | Label |
|---|---|
| `in` | "Vormoor · village" |
| `outside` | "near Vormoor · farmland" |
| road, when `scene.road` is set and `at` is `@along-…` | "on the road to Dustgate · most of a day out of Vormoor" |
| `under` | "under Vormoor · underground" |

The brief's HERE line becomes "HERE: outside Vormoor, a village of a few hundred…". THE
PLACES HERE splits into "IN VORMOOR:" and "OUTSIDE VORMOOR:", so each list stays short.

### 20.2: biomes grounded in the world

`_op_travel` with `biome` asks `geography.grounded(land, biome)`:

- `near` → allowed as today.
- `beyond` → allowed at the 4-hour band, handed through `_hours_underway` so
  `ontheway.road` checks those hours once.
- `absent` → **refused, and printed**: "There is no woodland near Vormoor. Outside it is
  farmland; mountain further out; the wider land is ash-fields and badlands." It carries
  Lane A's `fixable_by: "player"`.
- `unknown` → the world said nothing. Accepted and recorded, the three-way honesty `pace`
  already uses.

**How the Land is built:**

- `near` = `crosses[0]` of every road and river leg, plus `coast` for a port or a settlement
  whose own words put it on water (`places._WATER_WORDS`).
- `beyond` = `crosses[1:]` of those legs, then the ancestors' prose biomes, nearest first.
- Sea-leg `crosses` are excluded, because they describe the far shore: Vormoor→Moldwarren by
  sea "crosses" forest.
- Ancestor facts are read by a key **lexicon**, case-insensitive: *geography, terrain,
  landscape, biome, climate, region, environment, topography, land*. The synthetic world's
  continent says `Landscape`, and Pangrella's nations put real ground under `Region`.
- `geography` matches with a trailing word boundary, so "ash-fields" is no longer grassland.

### 20.3: every place has its own caption

- New `floorplan.BY_SPOT` rows for the ring slugs.
- `the-approach` becomes "the near edge of it, and little to hide behind".
- A test asserts that no caption contains another place's name from the same `for_scene`
  set. That is the defect as measured.

### 20.5: a road claimed only when walked

`gm/checks/road_claimed.py` flags "the road to X", "on the road", or "set out for X" (X a
settlement) when all three hold: no `journey` effect this beat, here is not X's road place,
and the reading has no `journey` act.

- **Repair:** "The party is at {here}; the road to X starts from {leaves_from}."
- **Backstop:** cut the sentence.

### The warrant at the way out

When the destination is `outside`, `_op_travel` applies the entrance check at any
entrance hop on the route, not only at the destination.

---

## 5. What the Phase-1 seams must provide

### S5: `rules/geography.py` (owned by B in Phase 2; C and D read it)

```python
@dataclass(frozen=True)
class Land:
    settlement_id: str
    near: tuple[str, ...]                 # biome words
    beyond: tuple[str, ...]               # biome words, disjoint from near, never "urban"
    words: tuple[tuple[str, str], ...]    # (whose, the world's own words), nearest first
    climate: str                          # world's words or ""
    water: str                            # settlement's own water phrase or ""
    coast: bool
    source: str                           # "exact" | "derived" | "unknown"

def land_around(world, settlement) -> Land
def grounded(land: Land, biome: str) -> tuple[str, str]
    # ("near" | "beyond" | "absent" | "unknown", redirect words or "")

@dataclass(frozen=True)
class Road:
    to_id: str
    to_name: str
    to_kind: str                          # "a town"
    how: str                              # "road" | "river" | "sea" | "sea-after-road"
    time_words: str                       # "about three days on foot"
    crosses: tuple[str, ...]
    crosses_words: str                    # "farmland, then mountain"
    leaves_from: str                      # "the outskirts" | "the docks" | "the shore"
    bearing: str                          # "" until exported
    source: str                           # "exact" | "derived"

def roads_out(world, settlement, speed_ft: int = 30) -> tuple[Road, ...]
    # wraps journey.legs_from and journey.hours_for: the brief's days are the engine's days

@dataclass(frozen=True)
class Where:
    setting: str                          # "in" | "under" | "outside" | "road"
    label: str                            # "near Vormoor"
    detail: str                           # "farmland"

def where(world, scene, here) -> Where
def walk_words(minutes: int) -> str
```

**G1's assertion should be sharpened** to: Vormoor has `near == ("farmland",)`, a `beyond`
starting `("mountain", …)`, three road legs and two sea legs, and no bearing. Pangrella's
town falls back to prose. The synthetic world's leg with no `by`, `miles` or `crosses`
produces no invented road facts.

### S2: brief registry

- **Member:** `ORDER: int`, `SCAFFOLD: tuple[str, ...]` (Lane A's ask), and
  `section(ctx: BriefContext) -> tuple[str, dict]`, returning the text and its facts.
- **`BriefContext`:** `world`, `scene`, `location`, `here`, `known`, `recent`, `secret`,
  `turn`, **plus `reading: dict | None` and `player_text: str`**. `scene_brief` gains those
  two kwargs and a `report: dict | None` out-parameter for the facts (the `prompts.pack`
  pattern), so the returned text stays byte-identical.
- **Move, don't add.** S2 moves today's HERE / PLACES / NEXT DOOR / UNDERFOOT block into
  `gm/brief/here.py` and the ROADS OUT line into `gm/brief/roads_out.py`, ordered to
  reproduce today's bytes. Otherwise Lane B's members would duplicate lines that only
  `prompts.py`'s owner may delete. Point `test_the_place_the_brief_states_comes_from_the_engine`
  at the moved code.

### S1: checks and `BeatContext`

Lane A's member shape, unchanged. Fields beyond Lane A's table:

| Field | Type | Used by |
|---|---|---|
| `was_at` | `str`, `scene.at` before the turn | route_walked, land_described |
| `known` | `tuple[Place, ...]`, after the turn | road_claimed |
| `world`, `location` | the loaded world, the settlement entity | all four |
| `brief_facts` | **`dict[str, dict]`** keyed by section module | land_described, bearing_invented |

Lane A asked for `brief_facts: list[str]`. The dict lets a check read the Land the brief
printed rather than derive it twice. The register should pick one.

S1 also owns two `agent.py` edits this lane needs:

- `turn_schema(places=...)` (line 403) routes through
  `interpret.travel_choices(self.reading, scene, places, location)`. It is inert at G1:
  today's tuple.
- `scene_brief` (line 302) gets `reading=self.reading, player_text=player_input`. S3 makes
  the same change on the prose-side call.

### S3: API keys

`/api/state` `scene` gains `where_label`, `where_detail` and `setting`, from
`geography.where`. `02-state.js:216` must print `where_label · where_detail` when present.
That file is unowned: assign it to S6 or F.

### S4: persisted fields

**Drop `Scene.outside`** (see §3.7). Lane B needs no new persisted field: `Scene.road`
holds progress, the ring is derived, and minted crossroads and fords go into
`Scene.founded`.

### Effect fields the travel ops emit

**`travel`** (kind `biome`). Every existing field stays; `went_by` stays names, because Lane
A reads it. New fields:

| Field | Type or values |
|---|---|
| `minutes` | int |
| `went_by_about` | `[{"name", "about"}]` |
| `setting`, `was_setting` | from `setting_of` |
| `direction` | `"out"` \| `"in"` \| `"along"`; answers Lane A's ask |
| `stopped_short` | bool |
| `meant_for` | str |
| `met_refs` | `list[str]` |
| `grounded` | `"near"` \| `"beyond"` \| `"unknown"` \| `""` |
| `road_to` | `to_id` when the destination is a road place |

**A refused biome** has `status: "refused"`, an effect
`{"kind": "refused-ground", "biome", "near", "beyond"}`, and Lane A's `for_a_person` and
`fixable_by: "player"`.

**`journey`** adds `from_id`, `setting`, `direction`, and `place` on every branch.

**`found`** adds `setting`.

---

## 6. Owned edits: the Lane B list

**Confirmed:**

- `places.py`: kinds, captions, the outside tier, `setting_of`, the ring in `for_scene`,
  `OUTSIDE_KINDS`, `fits_here`.
- `interpret.py`: `ops_for`, `travel_choices`, `_WHAT_EACH_IS`.
- `ontheway.py`: the street table for ring hops; minutes shared out pro rata.
- `_op_travel`, `_op_found`, `_op_venture`, `_op_journey`.
- The new files named in the plan.

**Add:**

- `Engine.places`, `Engine._terrain_hint`, `Engine._march`.
- `rules/journey.py: legs_from`, so that `by: "road"` means the road column.
- `rules/floorplan.py: BY_SPOT`.
- `rules/geography.py` in Phase 2.
- `gm/brief/here.py`, after S2 moves it.
- One assertion in `tests/test_one_spatial_authority.py`.

**Not Lane B's:** `02-state.js`.

---

## 7. World-agnostic notes and World Bible export asks

Nothing here keys on an Aurvantis name, id or label:

- Fact keys are matched by lexicon.
- Ground comes from `crosses`, which already uses the engine's biome words in all three
  exports.
- Settledness goes through `_settled`, never `kind == "CITY"`. The synthetic world uses
  `VILLAGE` and `TOWN`, and `biomes.from_world` still tests `CITY`, so `geography` must not
  lean on it.

Test worlds:

- **Vormoor:** rich `crosses`, stilt-water words, no port.
- **Pangrella:** a single sea leg, so the Land comes from prose and the ring has no roads.
- **Synthetic:** a `Landscape` key; one leg with nothing but endpoints; a river leg over
  swamp.

**Asks for `docs/from-world-bible.md`.** All are optional. The fallback above works without
them.

| Field | Where | Best shape |
|---|---|---|
| `bearing` | `play.travel` row | one of eight compass words, from `from` toward `to`, only when the author knows it. Never derived from `world_map.py` rings |
| `road` | `play.travel` row, when `by: road` | `highway`, `road` or `trail` |
| `leaves_by` | `play.travel` row | the id of the settlement place the route leaves from |
| `near` | `play.settlements` row | 1–3 terrain words in the `crosses` vocabulary |
| `coast` | `play.settlements` row | `true` / `false` |
| outside places | `play.places` | rows with `parent` = the settlement, non-urban `terrain`, `"setting": "outside"`. They replace the generated ring, as authored rooms replace the generated set |

---

## 8. Tests and the live `leave-town` script

**Unit tests** (`tests/test_b_*.py`, across three worlds). Each docstring records the
measurement it guards.

- `leave_goes_outside`: `leave: outside it` from the market plans `travel` to the outskirts,
  and the enum holds ring names only (replay turn 5).
- `walk_costs_minutes`: Vormoor market → way in costs 4 minutes (two hops); a city crossing
  costs about 30 ("08:00 after two crossings").
- `forest_refused_near_vormoor`: refused, and farmland and mountain are named. The synthetic
  world with no data accepts it as `unknown`.
- `outside_is_parsed_not_stored`: `setting_of` over every generated id, plus Bobby's, plus
  the ratchet.
- `crossroads_foundable_only_outside` (replay turns 6 and 7).
- `roads_out_brief`: days in words, no miles, no compass. Pangrella's block is sea only.
- `captions_distinct`; `road_column` (pending the owner); `warrant_at_the_way_out`;
  `stopped_short_on_the_road`.
- **Replay:**
  - turn 7 flags `bearing_invented` ("north to Dustgate") and `road_claimed`;
  - turn 9 flags `land_described`(b) ("crushed pine");
  - turn 5 flags `route_walked`.

**Live `leave-town`** (R0's script, from the Vormoor opening, serial queue):

| # | Line | Passes when |
|---|---|---|
| 1 | leave town, stand outside on the road | `setting_of(at)=="outside"`; clock +5–30 min; panel "near {town}"; one land detail; nothing "opens to receive you" |
| 2 | look for a bearing | BEARINGS briefed; at least one real road named; no compass word by a settlement |
| 3 | nearest crossroads, signposts | the crossroads exists (≥2 roads) or is founded; signposts name real destinations, in days |
| 4 | road away until the walls vanish | a road place or a journey; no unbacked road claim; no walls invented for a village |
| 5 | take in the land | at least one world land word; no absent ground |
| 6 | head into the nearest trees | Vormoor: shown as refused, naming the ground that is there. Synthetic (beech hangers): accepted |
| 7 | back to the gate | setting `in`, direction `in`; road hours charged if walked |
| 8–9 | watchman; across town | a stop is shown as a stop; the clock moves minutes |
| 10 | leave by the road until nightfall | a `journey`, days in words; clock +60 or more, so the pop-up fires |

**G2 bar:**

- 10 of 10 steps end where the engine says;
- 0 invented bearings;
- 0 accepted absent-ground moves;
- at least 8 of 10 outside beats carry a world land word.

---

## 9. Open questions for the owner

1. **Drop `Scene.outside`** from S4 and derive it from the id.
2. **Read `by: "road"` as the road column.** Vormoor→Dustgate would go from 38 hours to
   about 27. Every road journey gets shorter, including in live campaigns.
3. **Minute bands:** village 2, town 4, city 8 minutes per hop, and half a mile per ring
   hop. Accept or tune?
4. **A generated crossroads** wherever two or more roads leave. It is structural, like the
   way in, but the world did not write it.
5. **`beyond` ground reachable at 4 hours**, or refused until a journey?
6. **Bobby stands in an absent forest.** Load it as "near Vormoor · forest" (recommended), or
   heal it onto the fields?
7. **Walking back along a stopped road** is charged the walked hours. Confirm.
8. **Sea legs from a non-port stilt village** leave from the shore, or does the ruling add
   a landing?
9. **`02-state.js`:** give it to S6 or to F.

---

## 10. Phase 2: the owner's rulings, mounts, and what was built (2026-09-28)

The owner's Phase-2 answers (docs/fix-interfaces.md §4) override §4 above in two places.

**Q11 — a crossroads is not in a town.** §4's ring put "the crossroads" beside the
outskirts, the fields and the shore. As built (`rules/outskirts.py`), it is out on the road
network: the outskirts leads to the crossroads, and the crossroads to each road head. It
exists only where two or more overland roads lead to different destinations, one per
fork: a crossroads holds at most five roads (six ways on with the way back), and a sixth
road hangs off "the far crossroads". Journeys along those roads pass through it — the
journey tell says "Out by the outskirts, the crossroads and the road to X" and the effect
carries the names in `went_by`. A crossroads founded in play (`found kind=crossroads`) is
refused off a town room with the fix `{"kind": "go", "place": "the outskirts"}`.

**Q13 — journeys take days, and a horse changes it.** Research first, as CLAUDE.md
requires. Primary sources fetched 2026-09-28:

| Rule | Source | Text used |
|---|---|---|
| Hustle | AoN Rules ID=50 (CRB Movement) | "A character can hustle for 1 hour without a problem. Hustling for a second hour in between sleep cycles deals 1 point of nonlethal damage, and each additional hour deals twice the damage taken during the previous hour of hustling." "A character who takes any nonlethal damage from hustling becomes fatigued." |
| Running overland | AoN Rules ID=50 | "Attempts to run and rest in cycles effectively work out to a hustle." |
| Mounted movement | AoN Rules ID=50 | "A mount bearing a rider can move at a hustle. The damage it takes when doing so, however, is lethal damage, not nonlethal damage." "The creature can also be ridden in a forced march, but its Constitution checks automatically fail." "Mounts also become fatigued when they take any damage from hustling or forced marches." |
| A day | AoN Rules ID=50 | "A day represents 8 hours of actual travel time." |
| Mount speeds | AoN Table 7-9 | light and heavy horse 5 miles an hour, 40 a day; pony 4 and 32 |
| The horse | AoN Bestiary, Horse | hp 15 (2d8+6), Con 17, speed 50 ft |
| Getting one | Ultimate Equipment, Animals and Mounts | light horse 75 gp (110 combat trained), heavy horse 200 gp, pony 30 gp, riding dog 150 gp, camel 150 gp; stabling 5 sp a day; "can be found in most large cities", availability "as the GM deems fit". No hire price for a mount is listed (carriage passage is 3 cp a mile, a cart 1 cp) — I could not source a rule for hiring a horse |
| Tried and abandoned | 2e.aonprd.com Actions ID=515 | Pathfinder 2e replaced the doubling damage with a cap: hustle "for a number of minutes equal to your Constitution modifier × 10". Recorded, not adopted: this is a 1e table |

**The design, within the three laws.**

- The owner's multipliers are used as ruled: on foot = the route's time at walking pace
  (`journey.hours_for`, now on the road column, Q12); riding = half; galloping the whole
  way = a third. PF1e's own 50-ft horse would be 5/3 of a walker, not 2; the ruling wins,
  and the book supplies only *when the gallop has to stop*.
- A gallop is a hustle. Per day of eight travelling hours the first gallop hour is free;
  the second costs each mount one point of **lethal** damage and leaves it **fatigued**;
  fatigued, it cannot run (CRB Conditions), and an overland gallop is running in cycles,
  so the rest of that day is ridden. That last link is our reading, stated as ours. The
  camp between days is the sleep cycle that resets it. So a road of six walking hours or
  less is a third; a longer one tires the horse and falls back toward half —
  "fatigue kicks in if the journey is too far", by rule. `journey.mounted_hours` does the
  arithmetic; Vormoor to Dustgate is 27 hours on foot, 14 riding, 12 galloping (two days
  of blown horses).
- **Fatigue is an `ActiveEffect`** through the one applicator (`add_condition`, source
  `hustle`), timed at 8 hours of the clock (4,800 rounds — the book's "8 hours of complete
  rest"), so `Scene.advance` expires it and there is no second ticker. The damage goes
  through the mount's own `take_damage`. No number comes from a model: the journey op's
  `pace` param is a closed word (walk/ride/gallop) and every hour is the table's.
- **A mount is a creature in the party**: a bestiary horse, warhorse or pony
  (`journey.MOUNTS`) who travels with you (`bond.travels-with-you`) or is named in
  `with`. One per rider; a party short of mounts is refused with the walking time said.
  The brief's ROADS OUT tells the planner the `pace` words only when a mount is present.
- **How a party comes to have one** is designed, not built, because the files are other
  lanes': owned from the start (C, a background's mount → `_bring_in("horse")` with the
  bond), bought at the stables (I2: a stall line at `the stables`, 75 gp for a light
  horse, the ostler as keeper), hired (D/I2: the same creature with a daily wage in the
  scheme ledger; no hire price is published, so a stabling-scale price is a proposal for
  the owner). Nothing in the engine changes when those arrive: they bring a creature in
  through the one door and give it the bond.
- **Ground beyond the near land** follows the same pace rule (no 4-hour band): its
  distance is where the world's own routes put it — a road that crosses farmland then
  mountain puts the mountain half-way along it — at the road column's pace, marched in
  days with a camp between when it comes to that (`outskirts.beyond_hours`). Ground the
  world names only in prose stands half a walking day out.

**Also built as recommended:** Q10's minute bands, Q12's road column, Q14 (Bobby's forest
loads as "near Vormoor · forest"), Q15 (walking back charges the hours walked), Q16 (sea
legs from a dockless settlement on the water leave from the shore).

**Deviations from §4, with reasons.**

- Hops out on the ring use the road's table pro rata by minutes (at least 1%), not the
  street table: the ring is outside, and a cutpurse in the fields is the street's joke.
- Under-town ground (the sewers) keeps the road's table, as it always had; only `in`
  hops use the street table.
- The warrant's scope is "from inside to outside" by place or by biome, as the register
  corrected (§1.3 B3), except founded and ventured ground, which stays the "another way"
  the refusal names — otherwise the refusal's own fix would be refused.
- "Into the fields" and "to the shore" by biome go to those ring places; any other ground
  is open ground past the outskirts, walked through them.
- Travel by biome to beyond ground rides no horse: `travel` has no `pace` param
  (rules/intents.py is not this lane's), so riding is the journey's alone.
