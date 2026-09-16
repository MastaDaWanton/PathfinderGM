# Campaign export format

**Schema version 1.3.** Read this before writing anything that consumes a World Bible
world.

World Bible writes a reference work for a person to read. This export is the same
material shaped for a program: stable identifiers, relationships as references rather
than prose, and the relational layers as data.

Two files are written into the world's own folder, both from the same builder:

| File | For |
|---|---|
| `<world>-campaign.json` | The contract. Self-contained, versioned, readable anywhere. |
| `<world>-campaign.sqlite3` | The same data in tables, for querying rather than walking. |

Exporting is instant and calls no model. Nothing is invented — it is a projection of what
the world already contains.

---

## Read this first

```json
{ "schema_version": "1.3" }
```

Check it before anything else. The rule is ordinary semver:

- **MINOR** bumps add fields. Ignore what you do not recognise and keep working.
- **MAJOR** bumps change or remove the meaning of an existing field. **Refuse to load a
  major version you were not written for** rather than guessing.

## Identifiers

Every entity has an `id` — a 12-character hex string, written into the world's own files
the first time it is exported, and never changed afterwards.

**Save state against `id`, never against a name or a path.** Renaming is a supported
operation in World Bible and rewrites names everywhere, including folder names. A campaign
that recorded "the party is in Mirabalos" by name would break the first time the author
renamed that city; one that recorded `655b660088ea` would not.

Ids are unique within a world, not across worlds. Key your own storage on
`(world.name, id)` or on the file you imported.

---

## Top level

| Key | What it is |
|---|---|
| `schema_version` | The format, as above. |
| `generated_by` | `{application, version}` — which World Bible wrote it. |
| `exported_at` | UTC ISO-8601. |
| `world` | `{name, premise, secret, counts}`. `premise` is the axes the world was rolled from; `secret` is the foundational truth almost nobody in it knows. |
| `entities` | Every place, people and person. See below. |
| `chronology` | Dated events with their full accounts. |
| `trade_routes` | Who sells what to whom, and what it strains. |
| `factions` | Cross-border powers, with aims and weaknesses. |
| `unwritten` | Names the world mentions but has never written up. |
| `play` | The same material rearranged for a session. |

## `entities[]`

```json
{
  "id": "655b660088ea",
  "kind": "CITY",
  "name": "Mirabalos",
  "summary": "city",
  "parent_id": "431bd046b7d5",
  "path": "continents/kaelinora/nations/kaldrimia/cities/mirabalos",
  "facts":    { "Governance": "...", "Social Classes": "..." },
  "sections": [ { "title": "Urban Life", "paragraphs": ["...", "..."] } ],
  "links":    ["00573c434004"],
  "trade":    { "sells": "Iron ore from nearby mines", "buys": "Wheat from Vedrazhian plains" },
  "scale":    "city"
}
```

- `kind` is one of `WORLD`, `CONTINENT`, `PEOPLE`, `NATION`, `CITY`, `CHARACTER`.
  `CITY` covers every settlement scale, from metropolis to outpost — read `scale` for the
  actual size.
- `parent_id` is the containing entity (`null` for the world). It gives you the whole tree
  without parsing `path`.
- `links` are cross-references this entry makes to other entities, already resolved to ids.
- `facts` are short tagged values; `sections` are the prose, already grouped under
  headings.
- A `PEOPLE` is an ethnic group, not a place: it may span several nations or belong to
  none.

## `chronology[]`

```json
{
  "name": "The Great Stepping",
  "year": -1200,
  "summary": "One line.",
  "scope": "continent",
  "background": "What led to it.",
  "moments": [ { "name": "The Betrayal", "detail": "..." } ],
  "aftermath": "What it settled.",
  "figures":  [ { "name": "Kaelorien Vyrnys", "role": "clan leader", "entity_id": "..." } ],
  "entity_ids": ["..."]
}
```

`year` is a signed integer counted from the world's founding reckoning — negative for
before it — or `null` when the event is undated. All years across a world are comparable.
A figure's `entity_id` is `null` when that person has never been written up; look them up
in `unwritten`.

## `trade_routes[]` and `factions[]`

A route carries `origin`/`destination` with matching `origin_id`/`destination_id`, the
`commodity`, and four written fields: `acquisition` (how the goods are won), `demand` (why
the buyer needs them), `conduct` (how the exchange is actually done) and `friction` (what
it strains). Endpoint ids are `null` if the place has not been written up.

A faction carries `name`, `description`, `reach`, `aim`, `method`, `foothold` and
`weakness`.

## `play`

Nothing new — the same material in the shapes a session needs. **Deliberately
system-agnostic:** no rules, no statistics, no dice. Turning any of it into Pathfinder is
the consuming application's job.

| Key | Each entry |
|---|---|
| `settlements` | `{id, name, scale, sells, buys, tension, governed_by, parent_id}` |
| `cast` | `{id, name, role, home_id, home}` |
| `travel` | `{from_id, to_id, from, to, carrying, friction}` — a route is also a road between two places that demonstrably deal with each other. |
| `conflicts` | `{faction, wants, works_by, holds, undone_by}` — an aim plus a weakness is a plot with a way in and a way out. |
| `timeline` | `{year, name, summary}`, sorted, undated events last. |
| `races` | *(1.1)* The world's peoples as playable races — one per `PEOPLE` that carries an anatomy. See below. |
| `cards` | *(1.1)* Situation cards: index cards of facts a narrator may state as true. See below. |
| `places` | *(1.3)* The places inside a settlement — the rooms a party stands in. See below. |

### `play.races[]` (1.1)

One entry per `PEOPLE` entity that has a `people_anatomy` section. A people without one
gets **no** entry: treat it as a heritage of some other body rather than a species.

```json
{
  "id": "korvu",
  "name": "Korvu",
  "people_id": "fd4449bc9a64",
  "size": "medium",
  "speed": "normal",
  "body":     ["Korvu have avian-like wings and bodies.", "Korvu have four limbs ending in sharp talons."],
  "senses":   ["Korvu have enhanced echolocation abilities."],
  "movement": ["Korvu have avian-like wings and bodies."],
  "about":    "One paragraph, in the world's own words.",
  "strengths": ["strong", "perceptive"],
  "weakness":  "nimble"
}
```

- `size` is `small`, `medium` or `large`; `speed` is `slow`, `normal` or `fast`. **Words,
  never modifiers** — the consumer's own tables do the arithmetic.
- `body[]`, `senses[]` and `movement[]` are short sentences lifted from the people's own
  anatomy, one sentence per entry, **never containing a digit**. A sentence about wings
  lands in `movement[]` because wings are for moving.
- `id` is a slug of the name, stable across exports; `people_id` resolves to `entities`.
- *(1.2)* `strengths` is **exactly two** of `strong`, `nimble`, `hardy`, `clever`,
  `perceptive`, `commanding`, and `weakness` **exactly one** that is not a strength: what
  the people is good and bad at, in words, which a consumer prices as its ability array.
  **All three or none** — an incomplete array is ignored whole.
- Each sentence appears in **one** field only, says the thing and stops, and uses the
  world's words, never a rules term.

### `play.cards[]` (1.1)

An index card of facts about one live situation. One card per settlement with a recorded
tension; two per faction — a **public** card (what it is, where it reaches, where it
holds) and a **secret** one (what it wants, how it works, what could undo it).

```json
{
  "id": "pangrella-strain",
  "title": "Tensions between winged nobility and merchant castes",
  "facts": ["Tensions between winged nobility and merchant castes.", "..."],
  "keys": [],
  "tags": ["situation.world.pangrella"],
  "people": ["a0e2e99089ba"],
  "place": "5bbd0c40345f",
  "clock": "",
  "secret": false,
  "always_on": false
}
```

- **A fact is one sentence a narrator may state as true.** Never a digit, never a name
  the export does not contain — every fact is checked against the world's real names and
  dropped if it fails. Up to eight per card.
- A settlement card's `id` is keyed to the **settlement**, not the wording, so a
  regenerated tension keeps the same card.
- `tags` are hierarchical, dot-separated, lower-case. `keys` is left empty for the
  consumer to derive. `place` is the entity a card belongs to, or `null` for a faction
  whose foothold names nowhere the world knows.
- Nothing is made from `unwritten` — a card naming an entity absent from the export would
  be refused, and consumers make their own secret cards from that list.
- `always_on` is always `false` here; which card sits in front of the narrator every turn
  is the consumer's decision.

---

### `play.places[]` (1.3)

The places inside a settlement: the ground a party actually stands on, and the ground a
fight happens on. Up to **six** enterable ones per settlement — the ceiling is
`rules/places.MOST_SPOTS`, borrowed from Fate's two-to-four zones and Inform's "small
number of named positions", because every extra place is somewhere a narrator can strand a
player with nothing to do.

A place is **one room, not a building**. A house with a cellar and an upstairs is three
places joined by stairs; a market is one place however big; a city is not a place at all.

```json
{
  "id": "5bbd0c40345f~urban:the-market",
  "name": "the market",
  "about": "Windcatchers turning over every stall, and ironwork under noble seal.",
  "parent": "5bbd0c40345f",
  "terrain": "urban",
  "exits": ["5bbd0c40345f~urban:the-gate", "5bbd0c40345f~urban:the-workshops"],
  "described_only": false,
  "origin": "world",
  "size_ft": { "width": 100, "depth": 90, "height": null },
  "clutter": "dense",
  "footing": "firm",
  "vertical": "scatter",
  "storeys": { "up": 1, "down": 0 }
}
```

**The id carries the ground, and that is load-bearing.**
`{parent_entity_id}~{terrain}:{slug}`, with `^1` or `^-1` appended for a storey. The
consumer parses this and never looks anything up, so an id without its `~terrain` segment
describes a place standing on nothing and gets an empty twenty-by-twenty field instead of a
room. `terrain` is one of fourteen words and is repeated in its own field so a reader need
not parse an id.

| Field | Meaning |
|---|---|
| `id` | as above. Durable and unique across the export, and stable between exports — everything the campaign remembers about a place is keyed by this string |
| `name` | what people call it, lower case, article included |
| `about` | one sentence of prose the narrator may use. **No digits** |
| `parent` | the settlement or site entity id |
| `terrain` | the same word that is inside the id |
| `exits[]` | ids you can walk to. **Adjacency only — no distances, no weights** |
| `described_only` | `true` for a place named in prose that cannot be entered |
| `origin` | always `"world"` for anything exported; the consumer writes `"found"` and `"venture"` for its own |
| `size_ft` | `{width, depth, height}` in **feet**; `height` is `null` for open sky |
| `clutter` | `bare`, `some`, `cluttered`, `dense` |
| `footing` | `firm`, `broken`, `bad` |
| `vertical` | `ledge`, `slope`, `scatter`, `none` — how the place is shaped upward |
| `storeys` | `{up, down}`, counts of floors. Omit outdoors |

**Feet, never levels.** A room is eighty feet across under any ruleset; a *level* is the
consumer's own unit, and an export carrying one is silently wrong the day that unit moves.
Same reason `clutter` and `footing` are words rather than counts: how many pillars make a
room feel dense is a tuning number belonging to whoever runs the fight.

**Verticality has two halves.** More places should be shaped upward than not — but not all
of them. The consumer's own tables come out at 30 of 36, and the six it keeps flat are the
ones a reader would agree are flat: a sump, an alley between two walls, ploughed fields.
An export where nothing at all is `none` has a generator with no rule for refusing.

`docs/places-and-races-for-world-bible.md` is the full contract, including the three tiers
this can be shipped in and the cue words that already mint a place from a settlement's own
prose. `tools/check_places.py` checks an export against it.

## SQLite

Same data, one row per thing. `entities.facts` is a JSON string; `entities.prose` is every
paragraph joined with blank lines, for full-text search.

```
world(schema_version, exported_at, name, secret, premise)
entities(id PK, kind, name, summary, parent_id, path, facts, prose)
entity_links(entity_id, links_to_id)
events(id PK, name, year, summary, scope, background, aftermath)
event_moments(event_id, position, name, detail)
event_figures(event_id, name, role, entity_id)
trade_routes(id PK, origin, destination, origin_id, destination_id,
             commodity, sought_as, acquisition, demand, conduct, friction)
factions(id PK, name, description, reach, aim, method, foothold, weakness)
unwritten(name, kind, why)
races(id PK, name, people_id, size, speed, body, senses, movement, about,
      strengths, weakness)                                                -- 1.1, 1.2
cards(id PK, title, facts, keys, tags, people, place, clock, secret, always_on)  -- 1.1
places(id PK, name, about, parent, terrain, exits, described_only, origin,
       width_ft, depth_ft, height_ft, clutter, footing, vertical,
       storeys_up, storeys_down)                                                -- 1.3
```

In `races` and `cards`, list fields (`body`, `senses`, `movement`, `facts`, `keys`,
`tags`, `people`) are JSON strings; `secret` and `always_on` are 0/1.

Indexed on `entities.parent_id`, `entities.kind` and `events.year`.

```sql
-- every settlement in a nation
SELECT e.name, e.summary FROM entities e
  JOIN entities p ON e.parent_id = p.id
 WHERE e.kind = 'CITY' AND p.name = 'Kaldrimia';

-- what a place is caught up in
SELECT * FROM trade_routes WHERE origin_id = ? OR destination_id = ?;

-- the century before play begins
SELECT name, year, summary FROM events
 WHERE year BETWEEN ? AND ? ORDER BY year;
```

The export **replaces** the database file each time. It is an export, not a save: the
world's JSON stays the only source of truth, so keep campaign state — party location,
what the players have learned, what has changed — in your own file, keyed by these ids.

## Version history

- **1.3** — adds `play.places[]` and the `places` table: the rooms inside a settlement,
  with the ground in the id and the room's own size, footing and shape. Additive.
- **1.2** — a race card carries `strengths[]` and `weakness`; the `races` table gains both
  columns. Additive.
- **1.1** — adds `play.races[]` and `play.cards[]`, and the `races` and `cards` tables.
  Additive; a 1.0 consumer keeps working.
- **1.0** — first version.

## What is not here

- **No rules content.** No levels, no stat blocks, no encounter budgets, no dice.
- **No maps or coordinates.** Places relate through containment (`parent_id`) and trade
  (`travel`), not geometry.
- **No incremental sync.** Every export is a full snapshot; diff against your last copy by
  `id` if you need to know what changed.
