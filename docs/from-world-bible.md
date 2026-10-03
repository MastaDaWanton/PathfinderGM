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
