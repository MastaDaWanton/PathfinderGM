# Places and races: what World Bible has to generate for them to arrive playable

**Written 2026-09-15, from the Pathfinder GM side.** Companion to two documents that
already exist and are not replaced by this one:

| File | What it is |
|---|---|
| `docs/for-world-bible.md` | the full ask list, ordered easiest to hardest. Races are ask 1, places are ask 3, road distances are ask 6 |
| `docs/races-for-world-bible.md` | ask 1 in detail, plus `race-options.md`, `race-cues.json` and `check_race_cards.py` |
| **this file** | what a session must build **now**, with the places half rewritten for a consumer that measures distance and height — which it did not when ask 3 was written |

Two files travel with it and are meant to be copied into the World Bible repo:

| File | What it is |
|---|---|
| `tools/check_places.py` | a standalone checker. Run it on an export before shipping |
| `docs/place-vocabulary.json` | every word a place list may use, **generated** from the consumer's own tables by `tools/export_place_vocab.py` |

Canonical copy: `H:\coding\PathfinderGM\docs\places-and-races-for-world-bible.md`.

---

## Why this exists

Ask 3 was written on **2026-09-01**. Between then and now the consumer grew a third
dimension: rooms have floor plans, floors have height, a spider fights from a ceiling, a
fireball is a sphere with a top, and buildings have storeys joined by stairs. Ask 3 knows
none of that, and one of its examples is now actively wrong — see **B.1**.

The races half shipped in the meantime (schema 1.1, extended at 1.2) and needs no new
schema. It is in here because a session building both should know which half is settled.

> **Races: the contract is done. Read Part A, run the checker, do not redesign it.**
>
> **Places: the contract is not done. Part B is the work.**

## How to use this document

You are probably a session working in `H:\coding\WorldBible0.0`. You do not need to read
the Pathfinder GM codebase and you should not need to run it.

1. Read **The boundary** and **One format, two authors**. Everything below is shaped by
   them, and getting a field's type right and its spirit wrong is the failure mode.
2. Part A tells you whether the races you already ship are playable. It is short.
3. Part B is three tiers, each independently shippable. **Ship tier 1 first and stop**;
   it is the one that changes play most, and tiers 2 and 3 are worth nothing without it.

---

## The boundary that must not move

`docs/campaign-format.md` states it and a test in the World Bible repo asserts it: **the
`play` layer carries no rules.** No levels, no stat blocks, no encounter budgets, no dice,
no DCs, no modifiers, no prices.

> **World Bible supplies words. Pathfinder GM prices them.**

There are exactly two exceptions, and both are facts about the world rather than
quantities of any ruleset:

- **durable ids** — yours, already how everything is referenced, nothing works without
  them;
- **plain measurements** — how many miles of road lie between two towns (ask 6), and how
  many feet across a room is (**B.4**). A room is forty feet wide under every ruleset ever
  written. It is the same kind of fact as a settlement's scale.

A measurement is allowed. A *modifier* is not. `"height_ft": 20` is a room; `"ceiling": 4`
is the consumer's unit and you must not write it, because the day the consumer changes
what a level is worth, your export is silently wrong.

---

## One format, two authors

This is settled and you must not design against it.

> **World Bible will never author every place, and Pathfinder GM must still be able to
> make one during play. One format, two authors.**

The consumer mints places by three doors, and two of them survive whatever you ship:

1. **Implied** — a fixed table of cue words read from the settlement's own facts. *This is
   the door your work replaces.*
2. **Founded** — the player declares a base ("we set up at Marra's house") and the engine
   mints it with an owner. Stays.
3. **Ventured** — ground gone into: sewers, a cellar, a crypt, a cave, the rooftops.
   Stays.

So everything you author must be the same shape the app writes for doors 2 and 3, which is
why every place carries `origin`, and why **every field you add has to have a sensible
value when nobody authored it.** If a field has no derivable default, it is the wrong
field.

---

## What the traditions do, and what they abandoned

Checked 2026-09-15, because this is an interchange format between two programs and almost
nobody designs one of those from scratch any more.

**Universal VTT (`.dd2vtt`/`.uvtt`, Dungeondraft's export)** is the de-facto interchange
for VTT maps. It is **an image plus colliders**: a `resolution` block carrying
`map_origin`, `map_size` and `pixels_per_grid`, then `line_of_sight` and
`objects_line_of_sight` as coordinate polygons, `portals` (doors and windows), `lights`
and `environment`. Roll20, Foundry and Arkenforge all import it.

**It carries no elevation whatsoever.** That is the single most useful fact in this
section: the format the whole hobby standardised on is a flat plane, because a VTT's job
is to show a human a picture and let them see round corners. **Do not copy it.** This
consumer has no picture — it has a narrator and a rules engine — so an image is the one
thing it cannot use, and height is the thing it most needs.

**A proposed UVTT v2** is instructive in a different way. Its feature page advertises
"3D Bounds (Bottom/Top Z)" and "verticality" against v1's "Flat Plane", but the draft
specification I fetched states plainly that it *"contains no explicit Z-axis, floor-height,
or elevation fields"* and that **"levels are treated as separate maps, not as Z-layers"**,
with every geometry array nested under its parent map id — for *"absolute spatial safety
in multi-level dungeons"*. The advertised feature and the drafted one disagree, so treat
the 3D bounds as unbuilt. What it actually did ship is worth having: **levels are separate
maps keyed by id**, which is exactly what this consumer settled on independently — a
storey is a place with `^1` on the end of its id, reached by stairs.

**Foundry VTT** went the other way and it cost them. The *Levels* module modelled a floor
as a named elevation band (a bottom and a top), *Wall Height* gave each wall its own top
and bottom, and after roughly five years the functionality was absorbed into core as Scene
Levels and the module retired. The documented gotcha is the tell: with both negative and
positive levels in play, the background layer at elevation 0 is a solid plane that blocks
vision even when transparent. That is what retrofitting height onto a model that assumed a
flat plane looks like from the inside. (The module wiki returned HTTP 429 when I tried to
read it directly; the retirement and the band model come from the package listings and
secondary pages, so treat those two details as reported rather than confirmed.)

**Tiled** (TMX/TMJ) splits its world in two: **tile layers** for the grid environment and
**object layers** for things placed freely, with custom properties allowed on nearly
everything, and global tile ids valid only within one map. The split is the lesson — the
regular ground is dense and grid-shaped, the interesting things are sparse and named.

**Azgaar's Fantasy Map Generator and Watabou's Medieval Fantasy City Generator** are the
closest analogue to this pair, and they are two separate programs that learned to talk.
Click a settlement in Azgaar and Watabou builds its plan *taking into account its size and
location*; click Overworld in Watabou and Azgaar builds a world around the city. **The
world generator passes context; the plan is made downstream from it.** That is the shape
this handoff should have, and it is why Part B asks you for a room's *character* rather
than for its squares.

**Final Fantasy Tactics** is where the consumer's height model comes from: one height per
square. It buys galleries, daises, rooftops and "you cannot get up there", and it cannot
express an overhang, because nothing is ever *under* a walkable square in the same column.
That trade is already made and is not reopening.

### What all that buys

1. **Do not ship an image, and do not ship pixels.** Feet or nothing.
2. **A storey is a separate place joined by stairs, not a Z-layer.** Agrees with UVTT v2's
   own choice and with what the consumer already does.
3. **Height is one number per square of ground**, never a band attached to an object.
4. **Say what a room is like; let the consumer place the furniture.** Azgaar hands Watabou
   a size and a location, not a street plan.

---

# Part A — Races (shipped; this is a checklist, not a design)

Schema 1.1 added `play.races[]`; 1.2 added `strengths[]` and `weakness`. The shape is in
`docs/campaign-format.md` and does not need restating here.

## The authoritative vocabulary is generated — do not transcribe it

Four files travel together, and two of them are generated from the consumer's own table by
`tools/export_race_cues.py`:

| File | Use |
|---|---|
| `docs/race-options.md` | **the complete list** of every option a card has, for a person |
| `docs/race-cues.json` | the same list, for a program |
| `docs/races-for-world-bible.md` | the diagnosis and a worked rewrite |
| `tools/check_race_cards.py` | run it on an export before shipping |

Hand-copying any of that into a World Bible file is the mistake `CLAUDE.md` names
explicitly: the copy nobody looks at goes stale and keeps shipping. Point at the generated
files; regenerate them when the consumer's cue table moves.

## The five things that actually decide whether a card is playable

1. **A card produces a size, a speed, up to twelve traits and an ability array. Nothing
   else.** Any sentence matching none of the patterns is read, matched and discarded.
2. **The cue patterns are matched over `body[]`, `senses[]` and `movement[]` joined
   together.** Which field a sentence sits in changes nothing mechanically — the fields
   are for the human reading the card. Put the sentence where a reader expects it anyway.
3. **Never write a digit** in `body`, `senses` or `movement`. Write "they see in the dark
   as well as in daylight", never "darkvision 60 ft".
4. **`strengths` is exactly two and `weakness` exactly one**, from `strong`, `nimble`,
   `hardy`, `clever`, `perceptive`, `commanding`, and the weakness must not also be a
   strength. **All three or none** — an incomplete array is ignored whole and the race
   falls back to a generic spread.
5. **`size: large` is recognised and not granted.** The Race Builder allows Large for
   giants only, so the sheet stays medium and the consumer writes a `not_yet` line saying
   so. This is not a bug to route around.

## What is already true and does not need fixing

Six of the twelve traits do something in play today; the other six are recorded on the
sheet, shown to the player, and the engine has no wall to climb or air to fly through yet.
**Write them anyway.** They are true about the people, and they start working without the
card changing — a fly speed written today began working the day the engine grew a third
axis, with no export regenerated.

## Done when

- `tools/check_race_cards.py` runs clean over the export.
- Every `PEOPLE` with a `people_anatomy` section has exactly one race entry, and every one
  without has none.
- No digit appears in any `body`, `senses` or `movement` sentence.
- `strengths`/`weakness` are present and legal on every card, or absent on every card.
- Race ids are stable across two consecutive exports.

---

# Part B — Places (the work)

## B.0 What a place is

**A place is one room, not a building, and not a district.**

- A house with a cellar and an upstairs is **three places**, joined by stairs.
- A market is **one place**, however big.
- A city is **not** a place — it is the settlement entity that places hang off.

The consumer sizes a settlement by the `scale` the export already writes on it: a
**village of five**, a **town of nine**, a **city of eighteen** rooms plus the square and
four crossings that hold a city together. One number for a hamlet and a capital is what
made every settlement in every world the same six rooms, and it is gone. That ceiling is borrowed: Fate caps a scene at two to four zones and Inform's
Recipe Book calls for "a small number of named positions". An open-ended list is free text
wearing a tuple, and every extra place is somewhere a narrator can strand a player with
nothing to do — which is not an abstraction. Measured on Aurvantis: every settlement in it
has **four named people and one situation card**. At six places, two rooms already hold
nobody.

## B.1 The id grammar — and the bug in ask 3

Ask 3 gives this example id:

```
5bbd0c40345f:the-market
```

**That format is now wrong**, and it was right when it was written. The consumer settled
on one spatial authority at stage 8b, and the ground a place stands on lives **inside the
id**:

```
{settlement_or_site_id}~{terrain}:{slug}
{settlement_or_site_id}~{terrain}:{slug}^{storey}
```

`terrain_of()` parses it with no lookup and no world, which is what lets a deep-copied
scene answer "what am I standing on" and a save from an older build answer honestly with
nothing. Measured against the live code on 2026-09-15:

| id | what the engine builds |
|---|---|
| `5bbd0c40345f:the-windcatcher-yard` | **20×20 open ground** |
| `5bbd0c40345f~urban:the-windcatcher-yard` | 16×14 urban room, walls and clutter against them |
| `5bbd0c40345f~forest:the-windcatcher-yard` | 18×18, trunks and undergrowth |

A place the consumer happens to recognise by slug (`the-market`, `the-library`) survives
the old format by accident. **Every place World Bible invents a name for does not**, and
lands on the blank twenty-by-twenty field that the entire last fortnight of work existed
to remove. Get the `~terrain` in.

**Rules for the id:**

- `~` separates the location from its ground; `:` separates the ground from the slug; `^`
  introduces a storey. None of the three may appear in a World Bible entity id (checked
  against the fixture: they are twelve hex characters).
- `terrain` is one of the **fourteen** the consumer knows, and no other word:
  `coast`, `desert`, `farmland`, `forest`, `grassland`, `hills`, `jungle`, `mountain`,
  `planar`, `ruins`, `swamp`, `tundra`, `underground`, `urban`.
  A settlement's places are `urban` whatever the continent's facts say.
- The slug is lower case, hyphenated, and includes the article: `the-market`.
- **Ids must be stable across exports.** Everything the campaign overlay remembers about a
  place is keyed by this string.

## B.2 Tier 1 — the place graph (ship this first)

This is ask 3, corrected. `play.places[]`, one entry per place:

| Field | Meaning |
|---|---|
| `id` | as **B.1**. Durable and unique across the export |
| `name` | what people call it, lower case, article included: `"the market"` |
| `about` | one short sentence: what it is for, what it is like. Prose the narrator may use |
| `parent` | the 12-char entity id of the settlement or site containing it |
| `terrain` | the same word that is inside the id. Redundant on purpose — a reader should not have to parse an id |
| `exits[]` | ids of places you can walk to from here. **Adjacency only. No distances, no weights** |
| `described_only` | `true` for a place named in prose that cannot be entered — "an alley runs east" — so the narrator may mention it without the engine minting a node |
| `origin` | always `"world"` for anything you export |

```json
{"id": "5bbd0c40345f~urban:the-market", "name": "the market",
 "about": "Windcatchers turning over every stall, and ironwork under noble seal.",
 "parent": "5bbd0c40345f", "terrain": "urban",
 "exits": ["5bbd0c40345f~urban:the-gate", "5bbd0c40345f~urban:the-workshops"],
 "described_only": false, "origin": "world"}
```

**Exits are symmetric unless you mean them not to be.** A one-way exit is a cliff you can
jump down and not climb; if that is what you mean, say so in `about`, because the engine
will let the party walk into a place it cannot walk out of.

### What a settlement needs at minimum

The consumer's fallback produces roughly this set and an authored one must not be poorer:
somewhere to buy (**the market**), somewhere to sleep (**the tavern**), somewhere to leave
by (**the gate**), somewhere quiet (**the temple** or shrine), somewhere the trades are
(**the workshops**), somewhere nobody is watching (**the back streets**).

Then whatever this town actually has. **The world's own words already drive this**, and
you should know exactly which words, because the consumer reads them mechanically out of a
settlement's facts today:

| Words in the settlement's own facts | The place they mint |
|---|---|
| port, harbour, harbor, dock, docks, quay, wharf, fishing, ships, shipping, boats | **the docks** |
| river, bridge, ferry, crossing | **the bridge** |
| guild, guilds, guildhall | **the guildhall** |
| library, archive, archives, scriptorium, scribes | **the library** |
| walls, fort, fortress, `the keep`, `a keep`, castle, citadel, garrison | **the keep** |
| `the mine`, `a mine`, mines, mining, quarry, ore | **the mine head** |
| shrine, temple, cathedral, priests, prayers, faith | **the shrine** |
| `the well`, `a well`, wells, wellhead, cistern, fountain | **the well** |

If your generator authors a place list, **it must cover at least these** — a town whose
paragraphs say "port access" and then has no docks is the exact complaint that built this
table ("why did it not make a docks?"). Authoring gives you the chance to do better: a
name the world actually uses beats any of these generic ones.

**The backticked cues are phrases, and must be written as phrases.** A cue with a space in
it is matched against the text; a bare word is matched against the settlement's set of
words. That distinction exists because three of these words are also something else:

```
"well"  fired in 64 of 64 Aurvantis settlements, every one on "that works well enough in"
"keep"  fired in 16 of 64, every one on "tax-farmers who keep a cut of"
```

Not one real well and not one real keep. That is worse than noise — a settlement is capped
at six places, so a phantom takes a real one's slot. `mine` was narrowed the same way
before it could do the same thing, since it is also the possessive pronoun.

The cues stay plain strings rather than becoming patterns **because this list is an
interface**: `docs/place-vocabulary.json` is what the other side reads, and a regular
expression does not survive that trip legibly. The cost is that a literal cue is literal —
"a deep well" does not fire, where "the well" and "a well" and "wells" do. Write one of the
strings above and it works; the vocabulary file is generated from this exact table, so it
can always be checked rather than guessed at.

### Done when (tier 1)

- Every `CITY` has at least four places, all mutually reachable.
- Every id parses as **B.1**, with a terrain word from the list of fourteen.
- Every `parent` resolves to a real entity; every id in `exits[]` resolves to a real place.
- Settlements whose facts mention a port, a mine, a river or a library have the matching
  place.
- Ids are byte-identical across two consecutive exports of the same world.
- No place carries a distance, a travel time, or a numeric weight.

## B.3 Tier 2 — what the room is like

This is the new half, and the reason ask 3 needed rewriting.

Every place the consumer knows about gets a **floor plan**: a grid of five-foot squares
with walls, rough going, raised ground and a ceiling. It is derived where nothing authored
it — SHA-256 of the place id, so the same tavern has the same pillars for ever on every
machine without a byte in the save — from a small table of *characters*: a market is
sixteen by sixteen with seven knots of stalls and a cart to climb on; a library is stacks
to the ceiling with a gallery round them.

> **These five fields are READ, since 2026-09-16** (`rules/floorplan.from_world`). They
> were written and ignored for two releases, which is said plainly here because an author
> deserves to know which of their work reaches the table. What each one does now:
>
> | Field | What it becomes |
> |---|---|
> | `size_ft.width` / `.depth` | the grid, at five feet to a square, clamped to 6–24 squares — a 15-foot closet is a room but not a scene, and past 24 is more map than anybody reads |
> | `size_ft.height` | the ceiling in squares; `null` means no roof, and a place with no roof has no floors above it whatever `storeys` says |
> | `clutter` | how much of the floor is solid stuff in the way: 2% of squares for `bare`, 11% for `dense` |
> | `footing` | how much is difficult going: 2% for `firm`, 18% for `bad` |
> | `vertical` | the shape upward, used as written |
> | `storeys` | the floors themselves. Ashwatch's tavern is `{"up": 1, "down": 0}` and gets exactly one upper room; before this it was given an undercroft, an upper floor and a top floor off a seed |
>
> Two consequences worth knowing before authoring more. **Real rooms are smaller than
> invented ones**: across the 456 places in the two shipped worlds the median room went
> from 160 squares to 99 when these were read. And `about` is NOT read as a description of
> the ground — the consumer keeps its own phrase for that, because `about` on the market
> of Ashwatch is "A merchant oligarchy that outspends the nobility", which is a fact about
> the town and nonsense said of a floor.

**What to author is that character, not those squares.** Three measurements and three
words:

| Field | Meaning |
|---|---|
| `size_ft` | `{width, depth, height}` in **feet**. `height` is the ceiling, or `null` for open sky |
| `clutter` | `bare`, `some`, `cluttered`, `dense` — how much solid stuff is in the way |
| `footing` | `firm`, `broken`, `bad` — rubble, undergrowth, standing water, spoil |
| `vertical` | `ledge`, `slope`, `scatter`, `none` — **how the place is shaped upward**, below |
| `storeys` | `{"up": n, "down": n}` — how many floors above and below this one. Omit for outdoors |

```json
{"id": "5bbd0c40345f~urban:the-library", "name": "the library",
 "about": "Stacks to the ceiling, and a gallery round them.",
 "parent": "5bbd0c40345f", "terrain": "urban",
 "exits": ["5bbd0c40345f~urban:the-market"],
 "described_only": false, "origin": "world",
 "size_ft": {"width": 80, "depth": 70, "height": 20},
 "clutter": "dense", "footing": "firm", "vertical": "ledge",
 "storeys": {"up": 1, "down": 0}}
```

### The four vertical words

This is the field that matters most, and the one with no equivalent anywhere in the prior
art above.

| Word | What it means | Typical of |
|---|---|---|
| `ledge` | a raised band along one side with a rail at its lip to shoot over | a gallery, a landing over a hall, a wall-walk, a quay |
| `slope` | ground that climbs across the place | hills, a mountain path, an approach, dunes |
| `scatter` | isolated raised things, no rail — crates, rubble, a cart, roots | a market, a wood, a swamp, a vault |
| `none` | flat, and meant to be | a sump, an alley between two walls, farmland, open steppe |

**`ledge` is the default, and that is deliberate.** A room with something to stand on and
shoot from is a better fight than a floor, and most real places have one. Standing
instruction from the product owner, 2026-09-14:

> *"You should pressure the output of rooms and maps with verticality — not so much that
> every place has it even when it is silly, but so that the designs it thinks of are more
> likely to have verticality than not."*

So when generating: **reach for a reason to make it flat, not a reason to make it
vertical.** A library has galleries because that is where the upper shelves are. A keep has
a wall-walk because that is what a keep is. A tavern has a landing because the rooms are
upstairs. `none` is the exception that has to be justified — a sump is as low as it goes, an
alley is two walls and what is left between them, a ploughed field is a ploughed field.

### Getting the measurements right

- **Feet, always.** The consumer divides by five. Never write squares, levels, or a number
  of anything the rules count.
- **10 feet of ceiling is a house** — a person stands with a little air and nothing flies
  over anybody's head. **20 feet is a hall.** Below 10 is a crawl; be sure you mean it.
- `null` height means open sky, and the consumer treats the place as outdoors for
  everything that depends on it — including whether it can have storeys at all.
- Plausible ranges, from what the consumer derives today: a small room 20–30 ft across, a
  hall 60–90, a market or a wood 80–100. Nothing clamps an authored value yet — there is no
  reader — so keep to the range yourself. A 300-foot room makes a slow fight and a narrator
  that cannot say where anything is.

### Storeys

A building's floors are **separate places with `^1`, `^-1` on the end of the same id**, and
stairs are the only way between adjacent floors — you cannot step from the undercroft to
the top floor without passing the room between. The consumer generates and names them; you
do not need to author a place per floor. **Just say how many there are**, and only where
the world has an opinion: a library has an upper floor, a keep has two, a fisherman's hut
has none.

Omit `storeys` and the consumer rolls it off the id, as it does today.

### Done when (tier 2)

- Every authored place has all of `size_ft`, `clutter`, `footing`, `vertical`.
- No `size_ft` value is in squares, levels, metres, or anything but feet.
- Across a whole world, **more places have a vertical word other than `none` than have
  `none`** — and every `none` is somewhere a reader would agree is flat.
- Every indoor place has a non-null `height`; every outdoor place has `null`.
- No place claims storeys and open sky at once.

## B.4 Why a room is allowed to have a number in it

Rule 1 forbids numbers in the `play` layer, and every example it gives is a **rules**
quantity: sizes as modifiers, speeds in feet of movement, clocks in rounds, prices, DCs.

A room's dimensions are not one of those. "The hall is eighty feet long" is true whoever is
playing in it, is expressible without a word of Pathfinder vocabulary, and is the same kind
of fact as a settlement's scale or the mileage of a road in ask 6.

The line is **feet versus levels**. Feet are a fact about the building. A *level* is the
consumer's own unit — five feet of height, one square of a creature's body — and the day
that unit changes, every export that wrote it is silently wrong with nothing to catch it.
Write the world's measurement; let the consumer do its own arithmetic. The same reasoning
is why `clutter` and `footing` are words: how many pillars a room needs to feel dense is a
tuning number belonging to whoever runs the fight.

## B.5 Tier 3 — explicit squares (last, and possibly never)

For a handful of places, the exact layout is genuinely a fact about the world: a bridge is
a span with a drop on both sides, a gatehouse is two towers and a walk between them.

If you get to this, the shape is four sparse lists of `[x, y]` pairs on a grid whose origin
is the place's north-west corner, measured in five-foot squares, plus one heightmap:

| Field | Meaning |
|---|---|
| `blocked[]` | walls and pillars. Refuses movement, blocks sight, gives cover |
| `difficult[]` | rubble, undergrowth, mud. Costs double to enter |
| `floor{}` | `{"x,y": height_ft}` — how high the ground stands. **One number per square** |
| `parapet{}` | `{"x,y": height_ft}` — low obstacles by the height of their top: a balustrade, a counter, a cart's side |

**Sparse, not dense.** A place is mostly ordinary floor, and a 20×20 array of the word
"normal" is 400 entries a save file carries and a human has to read. This is the same
choice Tiled makes with its object layers and the consumer already makes internally.

**`parapet` is not a short wall.** A blocked square is solid at every height, so a gallery
rail drawn as `blocked` between an archer above and a man below reads as a wall and the
engine calls it total cover in both directions — the opposite of what a rail is for. A
parapet stops a line passing at or under its top and lets everything over it through. If
you draw a rail as a wall you will have made the fight worse than no rail at all.

**Do not attempt an overhang.** One height per square cannot express a walkable surface
with another walkable surface beneath it. That is what storeys are for.

**Ship tier 3 for at most a dozen named places in a world**, and only ones the world has an
actual opinion about. Everything else is better derived: a generated market has never once
been the thing a session complained about, and four sparse lists per place is a large
amount of data to keep stable across exports for very little gain.

## B.6 What not to do

- **Do not ship an image, or pixels.** The consumer has no canvas. Universal VTT is
  image-first because a VTT shows a human a picture; this one narrates.
- **Do not add coordinates or latitude.** `agent_engine/world_map.py` is a containment
  diagram — ring radius encodes depth in the tree, and the module says so itself: "a claim
  about structure, not about latitude". Exported as geography it would produce confident,
  precise, wrong distances, and nothing downstream would look wrong.
- **Do not weight the exits.** Fate shipped weighted zone borders and deleted them. The
  consumer refuses them by design; obstruction belongs in states and effects, not a cost
  table nobody would tune.
- **Do not model doors as objects.** UVTT has `portals` because a VTT needs to draw one and
  toggle it. Here an exit *is* the door, and a locked one is a state on the place, not a
  geometry primitive.
- **Do not author encounters, monsters, treasure or NPCs into a place.** Those come from
  the bestiary, the codex and the quest schemes on the consumer's side. A place is ground.
- **Do not author a place per floor.** Say how many floors; let the consumer name them.
- **Size a settlement by its own `scale`** — a village of five rooms, a town of nine, a
  city of eighteen. One ceiling for every settlement is what this app did until
  2026-09-15, and it was wrong in the way that matters: Aurvantis ships 16 villages, 32
  towns and 16 cities and all 64 got the same six rooms, so a capital was a hamlet with a
  different name.

  A city needs its quarters as well — see `within` below — because eighteen rooms in one
  flat list is seventeen exits in one prompt, which is exactly what the ceiling protects
  against. A village and a town stay flat and everything in them is adjacent to everything
  else, because a settlement you can walk across is what a settlement is.

  It is a note, not a refusal. A longer list is accepted and played.
- **Do not put a digit in `about`.** It is prose the narrator may repeat, and the third law
  is that no model is ever handed a number.

## B.7 Delivery

`play.places[]`, additive, schema **1.3**. A 1.2 consumer ignores it and keeps deriving, so
nothing breaks by shipping it early or partially.

The SQLite mirror, in the style of the existing tables:

```
places(id PK, name, about, parent, terrain, exits, described_only, origin,
       width_ft, depth_ft, height_ft, clutter, footing, vertical,
       storeys_up, storeys_down,
       blocked, difficult, floor, parapet)
```

`exits`, `blocked`, `difficult`, `floor` and `parapet` are JSON strings; `described_only`
is 0/1; `height_ft`, the storey counts and all of tier 3 are nullable, because tier 1 alone
is a complete and useful export.

Add to the version history: **1.3 — adds `play.places[]` and the `places` table.
Additive.**

### Delivered, and the two rulings that came with it (2026-09-16)

World Bible 1.15.0 shipped all of this, and asked two questions back. Both are answered in
`docs/campaign-format.md`; they are repeated here because this is the document an author
reads.

**The version is 1.4.** `within` and the scale vocabulary are both additive on the wire, so
nothing forced a bump — but a version is not only for fields that break a reader. A 1.4
export *guarantees* that `scale` is a word this consumer publishes and that a city carries
`within`, and a consumer cannot tell by inspection whether an unrecognised `scale` is a
word the supplier forgot to translate or a world that genuinely has no such settlement. A
number answers that where a field cannot.

**Send the six scales raw.** World Bible's generator knows metropolis, city, town, village,
hamlet and outpost, and 1.15.0 flattened them to this app's three on the way out. Stop: a
supplier that narrows its vocabulary on a consumer's behalf destroys a distinction nobody
can recover, and how many rooms a metropolis has is a question about how a scene is built —
which is this side's business, exactly as `terrain_of` parses an id and never looks
anything up. `rules/places.SCALE_ALIASES` does the mapping now (the same one, plus thorp,
small/large town and small/large city), `place-vocabulary.json` publishes it as
`scale_aliases`, and `tools/check_places.py` accepts those words silently. This side went
first on purpose: send the six whenever you like and nothing has to be sequenced.

## B.8 What Pathfinder GM does today without any of it

All three doors stay regardless of what you ship; authored places replace door one only.

1. **Implied** — the cue table in **B.2**, plus a generated base set per settlement scale.
2. **Founded** — the player declares a base and the engine mints it with an owner.
3. **Ventured** — ground gone into, generated from a seed: `sewers`, `cellar`, `crypt`,
   `cave`, `mine`, `tower`, `ruins`, `rooftops`, `alley`.

Every one of them already gets a floor plan with height in it. The gap authored places
close is not *"the rooms are blank"* — it is that a place is **discovered** and never
**authored**, so the narrator cannot be grounded against a list of places the way it is
grounded against a list of people, because there is no list.

---

## The order to build in

1. **Tier 1 for every settlement.** Ids in the corrected grammar, exits, the cue-table
   minimum. This alone is the biggest single improvement available to this pair of
   programs.
2. **Run an export and look at it.** Every id parses, every exit resolves, nothing is
   stranded.
3. **Tier 2 on the same places.** Three measurements and three words. Watch the verticality
   balance across the whole world, not per place.
4. **Tier 3 only where the world has an opinion**, and probably not at all in the first
   pass.

**Run the checker after every step.** `tools/check_places.py` takes an export and tells you
what the consumer would build from it:

```
python check_places.py <world>-campaign.json           # tier 1
python check_places.py <world>-campaign.json --tier 2
```

Copy it and `docs/place-vocabulary.json` into the World Bible repo; it imports nothing from
either program and needs only the standard library. It reports per settlement, exits
non-zero on a problem, and treats a missing docks in a port town as a note rather than a
refusal. The vocabulary file is **generated** from the consumer's own tables by
`tools/export_place_vocab.py` — regenerate it when they move, and do not edit it by hand.

It cannot tell you whether a place is *good*. It can tell you whether the list reaches the
table at all, which is the failure it was written for.

---

## Sources

- [Universal VTT (UVTT) support — Roll20 Help Center](https://help.roll20.net/hc/en-us/articles/41643201127831-Universal-Virtual-Tabletop-UVTT-Support)
- [Universal VTT — Dungeondraft guide](https://dungeondraft-encyclopaedia.gitbook.io/guide/final-steps/exporting-your-map/universal-vtt)
- [All about Universal VTT files — Arkenforge](https://arkenforge.com/universal-vtt-files/)
- [Universal VTT v2 specification](http://universalvtt.org/)
- [Levels — Foundry VTT package](https://foundryvtt.com/packages/levels)
- [Wall Height — Foundry VTT package](https://foundryvtt.com/packages/wall-height)
- [TMX Map Format — Tiled documentation](https://doc.mapeditor.org/en/stable/reference/tmx-map-format/)
- [JSON Map Format — Tiled documentation](https://doc.mapeditor.org/en/latest/reference/json-map-format/)
- [Medieval Fantasy City Generator — integration with Azgaar's Fantasy Map Generator](https://watabou.itch.io/medieval-fantasy-city-generator/devlog/46967/054-integration-with-azgarrs-fantasy-map-generator)
- [Azgaar's Fantasy Map Generator](https://azgaar.github.io/Fantasy-Map-Generator/)
