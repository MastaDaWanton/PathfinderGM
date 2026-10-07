# Handoff: what World Bible is, and what it hands you

Written at the end of the World Bible session that built the export, so the next
conversation starts warm. Read `campaign-format.md` next — that is the actual contract.

## What World Bible is

A Django + Electron desktop app that generates internally-consistent worlds for fiction and
tabletop play using local Ollama models. Repo: `H:\coding\WorldBible0.0`, released at
https://github.com/MastaDaWanton/World-Bible (currently 1.4.0).

- **File-native.** A world is a directory of JSON files. The files *are* the data — there
  is no database copy. Worlds live in `Documents\World Bibles\`.
- **Six tiers**, each generated knowing everything above it:
  `WORLD → CONTINENT → {PEOPLE, NATION} → CITY → CHARACTER`. `CITY` covers every settlement
  scale from metropolis to outpost. `PEOPLE` is an ethnic group, not a place — it may span
  several nations or belong to none.
- **A global layer on top:** a chronology of dated events with full accounts, trade routes
  between settlements, and cross-border factions.
- Generating a world takes about an hour on a local model. **A finished sample ships with
  the app**, and a copy of it is in `fixtures/` here.

## What you get

`Export for play` in World Bible writes two files into the world's folder:

- `<world>-campaign.json` — the contract. Self-contained, versioned, readable anywhere.
- `<world>-campaign.sqlite3` — the same data in tables, for querying rather than walking.

Both are in `fixtures/`, generated from the shipped sample world (Pangrella): 74 entities,
111 events, 5 trade routes, 5 factions, 47 characters.

Exporting is instant and calls no model. It is a full snapshot every time — there is no
incremental sync, so diff by `id` if you need to know what changed.

## The three things that matter most

1. **Save state against `id`, never a name or path.** Every entity carries a durable
   12-character id, written into the world's own files once and never changed. Renaming is
   a supported operation in World Bible that rewrites names *and folder paths* everywhere.
   A campaign that recorded "the party is in Mirabalos" by name breaks the first time the
   author renames that city.

2. **Check `schema_version` before reading anything.** Minor bumps add fields you can
   ignore; a major bump means refuse to load rather than guess.

3. **The `play` layer carries no rules.** `settlements`, `cast`, `travel`, `conflicts`,
   `timeline` — the shapes a session needs, keyed by the same ids, with no levels, stat
   blocks, encounter budgets or dice. **Turning any of it into Pathfinder is this app's
   job.** That boundary was chosen deliberately: baking one ruleset into World Bible would
   be a promise it cannot keep, and there is a test in that repo asserting no rules
   vocabulary leaks in.

## Known gaps in the data

Be defensive about these. They are real, they are documented, and they are not yours to fix
from here:

- **Section rewrites can invent places and people.** The faction rebuild is grounded
  against the world's real names, but a section rewrite is not — one produced "Aviari's
  Spire" and "Elyria's Forge", neither of which exists. Treat any name in prose as
  possibly fictional-within-the-fiction.
- **`entity_id` may be `null`** on a chronology figure or a route endpoint. That means the
  thing is named but has never been written up. Those names are collected in `unwritten`
  — offer them as blanks to fill rather than treating the reference as a dead end.
- **Missing-place detection only reads structured fields** (route endpoints). A place
  invented purely inside a faction's prose is not caught, so `unwritten` is not exhaustive.
- **No maps, no coordinates, no distances.** Places relate through containment
  (`parent_id`) and trade (`play.travel`), not geometry. If the game needs travel time, it
  has to invent it.
- **Years can be `null`** for undated events; the timeline sorts those last.
- **Names carry no gender, and neither do characters.** `play.names[]` gives each people
  one `given` list, and the characters are written as "them" throughout (Bregan Sootspar,
  measured 2026-09-27: 256 characters, not one "he" or "she"). So a townswoman the prose
  calls "a woman mending nets" can be named Soren Kragnirath, which reads as a man's name
  to an English reader and says nothing either way in the world's own language. This app
  does not guess a made-up name's gender from its shape; that would put English over the
  world's language, the trap the races ruling names. **Requested of the next export:** a
  gender (or none) on each given name, or given lists split the way the people split
  them. `rules/names.py:true_name` is where it would be read. The shape is in *Asks of
  the next export* below, with everything else this app would like.

## Asks of the next export

Collected 2026-09-28 from the playtest of that day (`docs/playtest-2026-09-28.md`, "What
World Bible should export") and the six fix-pass designs (`docs/design-a-truth.md` …
`docs/design-f-ui.md`, each design's §7). Written here once, so that no lane of the fix
pass has to edit this file again.

**Every one is optional.** The app builds a fallback for each from what the export already
ships, and a world without the field stays playable; the field makes it sharper. That is
the same promise `journey.py` made about `miles` before any export carried it. The rules
for the shapes, all learned the hard way:

- **Words, not numbers,** for anything a narrator will read. A number in the brief is one
  the model starts doing arithmetic with.
- **The world's own sentences,** unedited. The app puts labels around them and never
  rewrites them.
- **Structured fields over prose the app must parse.** Every fallback below is a parse of
  prose, and every parse has been wrong somewhere ("ash-fields" read as grassland).
- **Ids, never names,** for anything that points at another entity. Renaming rewrites
  names.
- **Nothing rules-shaped.** No levels, DCs or dice: the `play` layer still carries no rules.

Where the app already reads a field the moment it appears, the reader is named. The two
designs E (magic) and F (the table's furniture) asked for nothing.

### Where things are

The export has no maps, coordinates or distances beyond `play.travel`. On 2026-09-28 the
narrator invented "north to Dustgate, west to Grotburrow" and three of Vormoor's five routes
were never mentioned (playtest items 17 and 19).

| Field | Now | Best shape |
|---|---|---|
| `play.travel[].bearing` | Absent everywhere; the world records no direction at all | One of eight compass words (`north`, `north-east`, … `north-west`), from `from` toward `to`, and **only when the author knows it**. Never derived from `world_map.py`'s rings, which encode containment depth, not latitude. Read by `geography.roads_out` (reversed for a row walked the other way); anything else is dropped rather than guessed. Coordinates per settlement would answer the same need, and bearings are the smaller ask |
| `play.travel[].road` | 0 of 132 Aurvantis rows carry it, so every road is priced as trackless ground (Vormoor→Dustgate 38 hours, about 27 on the road column) | When `by` is `road`: `highway`, `road` or `trail`, the three columns of PF1e's overland table. Read by `journey.legs_from` today |
| `play.travel[].leaves_by` | Absent; the app says every road leaves from the outskirts | The **id** of the settlement place the route leaves from (its gate, its docks). Read by `geography.roads_out` |
| `play.travel[].miles` | Shipped on every Aurvantis row; missing on some synthetic rows, which the brief then states as "how far, nobody has written down" | A whole number on every row. It is the one number the app turns into words itself ("about five days on foot") |
| `play.settlements[].near` | Absent; derived from the first ground of every road out plus the continent's prose | One to three terrain words in the `crosses` vocabulary, nearest first: the land at the gate. Replaces the derivation outright (`geography.land_around`) |
| `play.settlements[].water` | Absent; inferred from being a port or from words like "stilt" and "tide" in the settlement's facts. Vormoor, a stilt village, is not a port | `"coast"`, `"river"`, `"lake"` or `""`. Design B asked for `coast: true/false`; this is the same fact with more in it, and `land_around` reads either |
| Outside places in `play.places` | None; the app will generate a small ring (the outskirts, the roads, a crossroads, the fields, the shore) | Rows with `parent` = the settlement's id, a non-urban `terrain`, and `"setting": "outside"`. They replace the generated ring, as authored rooms already replace the generated set |
| Landforms near a settlement | Absent. 2026-10-05, the owner's "i go up the mountain" from the road to Grotburrow founded a nameless "the mountain"; the app now stands such a place on the ground its own words name (`places.own_ground`, docs/place-doors.md), but it cannot know the mountain's name or how far it is beyond what `near`/`crosses` imply | Outside rows in `play.places` for the named land the settlement looks at — `{"name": "the Ashspine", "terrain": "mountain", "parent": <settlement id>, "setting": "outside", "miles": 12}` — with `terrain` from the `crosses` vocabulary. "Up the mountain" would then travel to the world's own mountain instead of founding one |
| `play.settlements[].landforms` | Absent. 2026-10-05, the owner: "everywhere has been farmland … this makes gathering tha materials i need for crafting impossible." 15 of Aurvantis's 64 settlements listed no ground outside but farmland and the shore within four hours; Vormoor's nearest other ground was eight hours out. The app now derives a **hinterland** (`geography.Reach`, docs/place-doors.md "The hinterland"): the roads' first ground at three miles, then the ground its nearest region's land facts name, at four (village), five (town) or seven (city) miles, unless a road puts that ground further. It can only use what the prose says, so it cannot name a wood the prose never mentions, and a continent-wide list ("scorched badlands, temperate savannas, arctic tundras") has to be thinned by rule. Read now by `geography._stated_reaches`; given, it replaces the derivation outright | Two to four named landforms within a short walk, nearest first: `[{"name": "Hob Wood", "terrain": "forest", "miles": 2, "words": "old oak and holly, coppiced by the village"}]`. `terrain` is a word from the `crosses` vocabulary (an open ground: forest, jungle, swamp, hills, grassland, desert, tundra, mountain; the fields and the shore are generated). `miles` is from the settlement's edge and at most a few hours on foot; ground further away belongs in `crosses`. `words` is the world's own clause for what it is like and is what the Places row and the narrator show. A farming village should have more than fields here: the historical record puts woods, pasture, meadow and waste within an hour's walk of almost every village |
| `play.places[].features` | Absent. Added 2026-10-03 (playtest item 9, docs/where-and-when.md): "head for the side door" founded *the smithy* and "move it toward the storage area" founded *the storage area*, because nothing said a counting house HAS a side door or a dock a storage area. The app now treats a room's fittings as things to walk to, from a fixed word list (`judgement._FIXTURES`); nothing reads this field yet | Per place, the few parts a person walks to inside it, each `{"name": "the side door", "leads_to": "<place id or empty>"}`. A feature with `leads_to` is a door: walking TO it stays in the scene, going THROUGH it is a travel to that id. Names are the world's own; never invented by the app |
| `play.settlements[].daylight` | Absent; the app's hour words assume a temperate day (dawn 3–8, dusk 16–21; `gm/checks/time_of_day.WINDOWS`), the same in every world | Words, not hours: `"long days"`, `"short days"`, `"even"`, or the world's own sentence about its sky (a world with two suns, or none, says so). The time-of-day check is where it would widen or narrow the windows; nothing reads it yet |

### People

| Field | Now | Best shape |
|---|---|---|
| `play.cast[].role` | `"Person"` on every row: 256 of 256 in Aurvantis, 47 of 47 in Pangrella, while each entity's own `Role` fact says "healer" or "border scout". Every background tie matched nobody and every campaign met Drenn Ironvale first (item 8) | The entity's short role noun, three words at most ("healer"); add `role_long` for the phrase ("Innovative developer and expert in magnetic shift adaptation"). `geography.role_of` reads the entity's `Role`, `Occupation`, `Profession`, `Position` or `Title` until then |
| `play.cast[].gender`, `play.names[].given` | No gender anywhere; the characters are written as "them" throughout (see *Known gaps*) | `given` as `[{"name": "Kael", "gender": "male" \| "female" \| ""}]`, or split lists as the people split them; and `gender` on each cast row. `""` is an answer, not a gap |
| `play.cast[].standing` | Absent | `"notable"` or `"common"`, so the app can take a market's master from the cast instead of minting one when the world already wrote one |
| `play.cast[].appearance` | `Appearance` is free prose ("carries an old scar earned young…", "Tall, dark-haired, with Zhilakai facial markings") | Fields beside the prose, which stays the world's own: `{"text": str, "age": "young" \| "middle" \| "old" \| "ageless", "hair": str \| null, "marks": [str]}` |
| `play.races[].body_slots` | Absent; a Pangrella Korvu has talons and wings, so "hands" and "hair" cannot be assumed | `{"hair": bool, "hands": "hands" \| "talons" \| "paws", …}`: which of a face's slots this people has at all |
| `play.settlements[].peoples` | Absent; inferred from each resident's Identity prose | `[people_id, …]`, majority first |
| `play.names[]` per settlement | Aurvantis ships 64 per-town pools (`home_id`; Vormoor's holds 16 families) that nothing reads yet; Pangrella ships none | A `play.names` row for every settlement, with `home_id`, and a gender on each given name as above |
| A keeper known by name (`play.places[].keeper`, or `play.cast[].keeps`) | Absent. Since owner ruling F1 (2026-09-30) every keeper goes by a descriptor ("the one behind the bar") until the player is told their name; the export cannot say "everybody knows the smith is Hal Dunmore" | On the place's row: `"keeper": {"name": "Hal Dunmore", "known": "publicly"}`; or on a cast row: `"keeps": "<place id>", "known": "publicly"`. A name with no `known` is the world's name and NOT public. Read by `keepers.publicly_known` today |
| `play.races[]` for every people | Pangrella ships one body (Korvu) for six peoples; a person of the other five has no body to draw. Until 2026-09-30 the app drew the first body on the list for them — a Korvu face on a Nirkor | One `play.races` row per PEOPLE, `body` included. Until then `names.appearance_for` gives a bodiless people its name and the person's own details only |
| A people's word forms (`play.races[].forms`, or on the PEOPLE) | Only the bare name ("Korvu"). The app cannot say "one of the Korvu" or "a Korvu woman" without guessing a plural or an adjective, so its face line reads "is of the Korvu people"; and in 2026-10-03's playtest (item 14) "is a Korvu" was copied by the narrator as "a man named Korvu" and taken for a person's name | `{"singular": "Korvu", "plural": "Korvu", "adjective": "Korvu"}` — the world's own spellings, which no English rule can derive for an invented people. Every PEOPLE name is already refused as a personal name (`names.people_names`, read from the PEOPLE entities and `play.races`); the forms would let a refusal also catch "Korvus" or "Korvan" |
| A person's name for everyone made in play | Pangrella ships no `play.names` (above), so a person whose name a bad page took (c11, renamed "Korvu") is healed on load with NO true name: asked, he has none to give | The per-settlement pools above. Until then such a person keeps their descriptor and no name |
| A people that robs the road | Read from the people's own facts (Pangrella's Nirkor: "Status: Nomadic herders, occasional raiders"); Aurvantis and the synthetic world name none, and their caravan raiders are the local people | A tag on the PEOPLE (`"outlaws": true`) or `play.settlements[].threats: [people_id]`, so the app need not read "raiders" out of a sentence. Read by `openings.outlaw_people` |

### How a settlement talks about itself

| Field | Now | Best shape |
|---|---|---|
| Stock sentences | Scale-blind: all 64 Aurvantis settlements say "drawn… from the city's own leading families", and 48 of them are villages or towns. The opening called Vormoor, a village, "a sprawling settlement… the city's bustling thoroughfares" (item 1) | Stock sentences keyed on `scale`. `geography.in_its_own_words` rewrites "the city('s)" to the scale word until then, and never "the city of X" |
| Fact key `Urban Life` | On every settlement, village or not | A scale-free key (`Daily Life`, as the synthetic world writes). `geography.display_key` shows it that way until then |
| `kind` | `CITY` on every settlement (World Bible's word for "settlement"; the path is `…/cities/…`) | Documented in `campaign-format.md` as meaning "settlement", or a real kind per scale. The app reads `scale`, never `kind == "CITY"` |

### Trade and hooks

| Field | Now | Best shape |
|---|---|---|
| `play.settlements[].trade` | One `sells` and one `buys` line per settlement (Vormoor "iron"; Pangrella "Fine ironwork and crafted windcatchers"), and one keeper per market | `{"stalls": [{"line": "cord and canvas", "about": "<one sentence>"}], "authority": {"title": "clerk of the market", "answers_to": "<office>"}, "market_days": "<words>"}`. Lines as the world's own trades; words, not prices |
| `play.cards[]` | Absent; hooks come only from this app's schemes | `{"giver", "want", "offer", "motive", "withholds"}`, so a world's own hooks arrive in the same shape a scheme's do. `giver` is an id |
| `unwritten[].where_id` | `unwritten` names things with no location | The id of the settlement or place the unwritten thing belongs to, so it can be offered where it would be found |
| Where beds are let (`play.places[].lodging`) | Absent. Added 2026-10-03 (playtest item 25): an opening errand "Find a bed you can pay for" never put a bed within reach. The app now takes the settlement table's `lodging` slot (the tavern, then the inn, or a founded place of either kind) and prices a bed at the Core Rulebook's common inn stay, 5 sp | On a place that lets beds, its quality as a WORD: `"lodging": "poor" \| "common" \| "good"` — the book's three inn stays (a floor by the hearth, a raised heated floor, a private room). A word, not a price; the app owns the number. A settlement with none says so with no row. Read by `cards.where_met` today, by place name and kind |

### Things, what they are worth, and whose they are

Added 2026-10-03 by Lane A of that day's playtest (`docs/items-have-owners.md`). A thing
the world never priced — a crate of cargo at the docks, a merchant's pack — sells at this
app's own bottom rung (`pricing.UNLISTED_GP`), because the Core Rulebook prices only what
its tables list and the export says nothing about what a place's goods are worth.

| Field | Now | Best shape |
|---|---|---|
| `play.settlements[].trade.goods[]` | Absent; `trade` is one `sells` and one `buys` line of prose | One row per good the place trades in: `{"name": "salt fish", "worth": "cheap" \| "common" \| "dear" \| "precious", "kind": "food" \| "cloth" \| "metal" \| "stone" \| "timber" \| "other"}`. Words, not prices: the app would map `worth` onto the PF1e Trade Goods table, which sells at full value (Core Rulebook p.140). No reader yet; `pricing.goods_worth` is where it would go |
| `play.places[].props[]` | Absent; the props ledger (`Scene.props`) starts empty in every place | The things that lie in a place before anybody arrives, as `{"name": "a rack of oars", "owner": "<cast id or empty>"}`, to be laid into `Scene.props` at the place with its `owner`, so a take of one is a take from somebody and not a thing out of the air. No reader yet |
| `play.cast[].carries[]` | Absent; the app reads a person's hands only off a label like "the merchant with a heavy pack" (`holding.carried_by_label`) | A few words per thing a person is known to carry ("a ledger", "the harbour keys"), so a take from them is a take of something they actually had. No reader yet; `Engine._holder_of` is where it would go |

### Ingredients and reagents

Added 2026-10-02 by the herbalism revamp. The export carries no flora at all, so every world
gets the shipped corpus of 161 herbs and parts, and a world's own plants exist only in its
prose. The proposed shape is `play.flora[]` in `campaign-format.md`.

| Field | Now | Best shape |
|---|---|---|
| `play.flora[]` | Absent. Fifteen shipped herbs are marked world flora (`ingredients.WORLD_FLORA`) because whether a world has them is the world's call | One row per plant, fungus or creature part the world names, with `about` in the world's own words, `grows_in` in the fourteen terrain words, and `rarity` |
| `play.flora[].part` | Absent | One word from the part list, read off the world's own description ("the bark", "the sap") |
| `play.flora[].uses[].route` | Absent | One word per use: `ingest`, `skin`, `eyes`, `wound`, `inhale`, or `external` for a use that reaches outside the body |
| `play.flora[].hybrid` | Absent | `true` when any use is magical, so the alchemist's shelf carries it too |
| `base_for`, `solvent`, `neutralizer` | Absent | Only on the few things that are bench reagents: a wax, an oil, a spirit, a lime. A world's own trade goods are the natural source (`trade.sells` already names them in prose) |

### Metals and the smith's materials

Added 2026-10-04 by the blacksmithing revamp (plan §15.1; fixes are world-agnostic). The
export carries no materials, so every world smiths the shipped shelf of 112 (iron, steel,
mithral, the skymetals and the rest), and a world's own metals — Pangrella's "fine
ironwork", any "blue iron of the eastern hills" — exist only in its prose. The proposed
shape is `play.materials[]` in `campaign-format.md`, the same document the shipped rows
are.

This is the one ask that carries numbers, and it is still optional. The app's own
validator holds a world's rows to the fences the shipped ones meet (house numbers start
at ±2, a tier ceiling, at least one drawback per list, nothing narrative), and reports a
row it refuses. If numbers are unwelcome on the World Bible side, the words alone are
still worth sending: a row with `name`, `kind`, `tier`, `text` and `biomes` puts the
world's own metal on the shelf by its own name, and `material` pointing at a shipped id
links the two as one material for knowledge and prospecting. What it does at the forge
then comes only from the effect lists the row carries — a row with none is inert there,
never given the shipped metal's numbers by guess.

| Field | Now | Best shape |
|---|---|---|
| `play.materials[]` | Absent. Every forge works the shipped shelf | One row per metal, alloy, ore, fitting, fuel, flux, quenchant or finish the world names, with `text` in the world's own words and `biomes` in the fourteen terrain words |
| `play.materials[].material` | Absent | The id of the shipped (or world) material this is a form of, when it is one: an ore names its metal, "the guild's mithral fittings" name `mithral` |
| `play.materials[].pieces` | Absent | Which slots it fills: weapon `head`/`haft`/`fittings`, armour `body`/`fastenings`/`lining` |
| `play.materials[].weapon`, `.armour` | Absent | At least three effects each where `pieces` names that gear, at least one a drawback, in the effect vocabulary; house numbers at ±2 |
| `play.materials[].working` | Absent | At least one working trait (`forgiving`, `slaggy`, `narrow_window`, `reactive`...) |
| `play.materials[].quench_mark` | Absent | Quenchants only: one small effect |
| `play.materials[].forms`, `feeds`, `finishes`, `not_on`, `book`, `assay_danger` | Absent | As `campaign-format.md` describes; all default sensibly, and `book` stays `false` for a world's own metal |
| `play.materials[].kind` + `.biomes` + `.obtain` | Absent | **Read by every trade's gathering since 2026-10-06** (the one gathering door, `content/rules/gathering.json`): `obtain` says which excursion can find it (`mined`, `gathered`), `biomes` where, and `kind` which trade goes out for it — an `ore` or `metal` comes to the smith's prospect in full batches and to the alchemist's quarry at half, a `salt` or `reagent` the other way round. How many of a trade's own kinds a ground holds also sets that ground's DC for the trade (none: 20, one to five: 15, six or more: 10), so a world whose hills hold six ores of its own makes its hills easy prospecting. No list of where things are found is needed beyond each row's own `biomes` |

### What an enchanter needs from a world (enchanting revamp, lanes B, D and H)

Collected in one place 2026-10-06 (lane H) from what lanes B (the layer and the material
tag) and D (the essences) asked on 2026-10-05, under the standing instruction that fixes
are world-agnostic. The enchanter puts a **layer** on an item someone else made, paid for in
**essences**, and asks of what the item is made of. A world gives all three their names and
their places; the numbers stay the app's.

The owner's rulings that bind every row: **phases of the day, never planets** ("this is not
earth"), so an essence's family favours `dawn`, `morning`, `noon`, `afternoon`, `dusk`,
`night` or `midnight` and **nothing asks the world for a sky**; **an essence's tier is its
price band**, computed from its motes, never chosen; and **what magic does is the book's**
(every property is a row of the app's table, `content/rules/magic-properties.json`), so a
world names which properties its essences and items carry and never invents one.

**What it is made of** (lane B: the material tag, `rules/item_tags.py`). One question,
"is it metal, and which metal", serves heat metal, the druid's rule and the enchanter's
surcharges, and it is answered from data, never a name.

| Field | Now | Best shape |
|---|---|---|
| `play.materials[].kind` | Absent (the whole of `play.materials[]` is proposed) | The substance for anything a piece can be made of: `metal` or `alloy` (both metal), `hide` or `leather`, `thread` (cord), `wood`, `bone`, `horn`, `cloth`, `stone`, `glass`. A world's "blue iron of the eastern hills" with `kind: "metal"` is metal to every spell that asks. The forge's other kinds (`fuel`, `flux`, `quenchant`, `fitting`, `treatment`) say what it does at the bench, not what it is |
| `play.materials[].material` on a fitting | Absent | **Required on a fitting** (and any form): the root material it is made of, `"material": "brass"`. A fitting's kind is only "fitting", so this link is the one way the tag learns that "the guild's riveted grips" are brass and metal. Without it the fitting is made of nothing the tag can name, and nothing is guessed |
| `play.materials[].enchant_surcharge_gp` | Absent | Only for a metal that should resist magic, as the book's cold iron (+2,000 gp the first time a weapon of it is enchanted) and noqual (+5,000) do: the extra gold, which the app turns into motes. Absent is no surcharge |

**Essences** (lane D: `materials.essences()`, checked by `materials.essence_problems`). The
enchanter binds essences, and a world's own creatures and places are where the found ones
come from. A world essence is a `play.materials[]` row with `kind` `essence`, shaped as
`campaign-format.md` ("A world's essences") describes.

| Field | Now | Best shape |
|---|---|---|
| `play.materials[]` rows of `kind` `essence` | Absent: every enchanter binds the shipped 93 | One row per essence the world names, `text` in its own words; `from_creature` (the world's creature) or `biomes` (the fourteen terrain words) for where it is found. **Ids are forever**: a bound item names its essence by id and reads its top-ups live from it |
| `.grants` | Absent | A property id from the app's table (with its `choice` when it asks one, `{"energy": "fire"}`, and a `bonus` for a scaled one), an enhancement step 1 to 5, or nothing (a mote supply). Never a new property |
| `.motes`, `.tier`, `.price_gp` | Absent | Computed by the app's rules (`materials.grant_motes`, `essence_tier`): World Bible may run them before export or leave `tier` and `price_gp` out for the app to refuse with the fix named; never a guessed number |
| `.family`, `.phase` | Absent | A shipped family (`fire`, `cold`, `holy`, `shadow`...), whose phase is taken from the app; or the world's own family, which **must** name its own `phase` |
| `.polarity` | Absent | Where it wants to sit: `weapon`, `armour`, `ward` (rings, cloaks, belts) or `any` |
| `.house` | Absent | The essence's own small flavour on top of the book: at least one typed top-up, each `"house": true`, inside the tier's ceiling (common and uncommon ±1, rare and exotic ±2, legendary ±3), drawbacks included. Never `narrative`, never one of the magic-item types still waiting on a reader. Scaled at bind time by the binding's quality, read live |
| `.working`, `.affinity`, `.color` | Absent | As the shipped rows: circle traits (`night_only`, `eager`, `skittish`, `heavy`, `volatile`, `pure`), the material ids that suit it, the glow on the stage |
| creature harvest tags | Absent | The leatherworker's harvest tags extended to essences (`harvest.essence.fire` on a world's fire creature), so a slain creature yields its family's essence by the same reader. **Reader built 2026-10-06** (`rules/gathering.py` `harvest_tagged`, every carcass excursion): `harvest.<branch>.<material-id>` on the creature's `tags`, branches `hide`/`horn`/`bone`/`sinew`/`scales` (leather), `blood` (forge), `reagent` (alchemy), `essence` (enchanting), `part` (herbalism); a tag naming no material on that craft's shelf is ignored; a creature with none is matched by name as before |

**A world's own named magic items** (lane H). An heirloom blade, the ring every reeve
wears: `play.magic_items[]` in `campaign-format.md`, shaped as the app stores an enchanted
item — a table `base`, optional `pieces` from the world's materials, and a `magic` block of
**ids and choices only** (enhancement, properties by id, recipe powers, an optional curse),
with `owner_id` or `where_id`. No reader yet.

| Field | Now | Best shape |
|---|---|---|
| `play.magic_items[]` | Absent: a world's named magic items exist only in prose | One row per item the world names, its `text` the world's own sentence; never a number |
| `.magic.properties[].choice` | Absent | **Every choice named**: bane's foe (a creature type, or the world's own subtype as `{"subtype": ...}`), resistance's energy, skill competence's skill and bonus. Learned 2026-10-06 converting old saves: the old catalogue's bane never named its foe, every reader applied it to every creature, and the conversion now has to stop and ask the player. An export can simply say |
| `.magic.curse` | Absent | A row of the book's curse table (`content/rules/curses.json`, the owner's dropped rows excluded), hidden until identified. Optional |
| knowledge chain | Absent | The item's history as questions a player can learn by study (plan §12.3, Earthdawn's thread items). Not designed yet; nothing should be exported for it before the app says how |

### What a trade keeps on its counter

Added 2026-10-05 (the owner: "the most important thing for places like the smithy to sell
are items to use as fuel for the furnace and other things consumed in crafting like water
vinegar and alcohol"). The app now decides which counters always carry each craft's
consumables — fuel, flux and quench at the smithy, the armorer and the market's curio
stall; solvents, salts and vials at the general store and the alchemist; bark, oil, wax,
thread and curing salt at the tannery — in its own table, `content/rules/stall-lines.json`
`consumables`. Which materials count is read off their `kind` (`fuel`, `flux`,
`quenchant`, `solvent`, `tannin`...), common tier only, so nothing here is per-world yet:
every world's smithy sells the shipped charcoal, coal and peat. A world that wants its own
says so in two places, both words, never prices.

| Field | Now | Best shape |
|---|---|---|
| `play.places[].supplies[]` | Absent. A place's keeper sells what the app's table gives its kind (`smithy`, `tannery`, `workshops`); a world's "Hessa's charcoal yard" is a place with a keeper and sells general goods | The crafts whose working supplies this place's keeper always has, from the app's four: `"supplies": ["blacksmith"]` (also `alchemist`, `leatherworker`, `enchanter`). An empty list is "sells none", absent is "the app's table decides". No reader yet; `market.consumables_at` is where it would go |
| `play.materials[]` rows of a consumed kind | Absent (the whole of `play.materials[]` is proposed, above) | A world's own fuel or quench as a `play.materials[]` row with `kind` `fuel`, `flux`, `quenchant` (or for the other crafts `solvent`, `salt`, `catalyst`, `vessel`, `tannin`, `oil`, `wax`, `thread`, `ink`, `chalk`, `treatment`) and `tier` `common`. Such a row is a staple on every counter that sells that craft's supplies the day `play.materials[]` has a reader, and it must carry `price_gp` or it is on no counter: the app refuses an unpriced common consumable in its own catalogues for exactly that reason (0 days of 60 for curing salt, measured) |
| `play.materials[].price_gp`, any kind | Absent | A number World Bible can check before it exports, by the app's one price rule (`rules/pricing.py`, `material_floor`; `campaign-format.md`, the `price_gp` row): at least the rung's floor — common 1, uncommon 5, rare 25, exotic 125, legendary 625 gp — ×5 for an essence, catalyst, ink, chalk, focus or neutralizer, × the row's strength above its rung; a rarer row never cheaper than a commoner one of its kind, a stronger one dearer than a weaker one. A world's "fen-salt neutralizer" priced like its water would be refused with the floor named. 1 cp is "free", for a plain common thing only. Leave `price_gp` out for a thing the world does not sell; never write a guess to fill the field |

## Things worth stealing

Patterns from World Bible that solved problems this app will hit too:

- **Per-field locks.** A generated entry usually has one part worth keeping and three worth
  another try. Locking the whole entry to protect one of them means never improving the
  rest, so every field — and every individual moment in an event — locks on its own, and
  regeneration skips what is pinned.
- **One instruction box, two buttons.** "Rewrite" replaces, "More detail" appends, and both
  obey the same typed instruction. Users type what they want and press whichever button;
  having one of the two ignore the box was a real bug.
- **Cancellable background jobs with live progress.** Generation blocks nothing; every long
  job can be cancelled and reports where it is.
- **Snapshot before every write.** Every save and regeneration writes a history snapshot
  first, so any step is undoable.
- **Pin what does not exist yet.** When generation names something that has no entry,
  record it as pending with a parent rather than dropping it, and offer to create it later.
