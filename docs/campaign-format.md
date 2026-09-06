# Campaign export format

**Schema version 1.0.** Read this before writing anything that consumes a World Bible
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
{ "schema_version": "1.0" }
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
| `cards` | `{id, title, facts[], keys[], tags[], people[], place, clock, secret, always_on}` — situation cards, see below. **World Bible does not write these yet**; the consumer derives a settlement's strain and each unwritten hook into cards when the list is absent. |

### `play.cards[]` — situation cards

A situation card is an index card of facts about one situation in the world, kept
by the game engine and shown to the narrator whenever the situation is in play.
Everything on it is the world's own sentence; nothing is a rule or a number.

| Field | Meaning |
|---|---|
| `id` | durable, unique within the export (`salt-levy`) |
| `title` | one line, under 80 characters: "The salt levy is due and nobody can pay it" |
| `facts[]` | up to eight short sentences the narrator may state as true |
| `keys[]` | trigger words; optional — the consumer derives them from the title and facts when absent |
| `tags[]` | hierarchical, dot-separated; the consumer prefixes `situation.world` when none begins with `situation.` |
| `people[]` | entity ids of the people the situation concerns |
| `place` | the entity id of the settlement or place it belongs to, or empty for anywhere |
| `clock` | how many steps it is from changing (default 4) |
| `secret` | the GM's alone — never stated to the player until play reveals it |
| `always_on` | in front of the narrator whether or not a key appears |

The consumer's side of the contract is `rules/cards.py` and `docs/situation-cards.md`.

---

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
```

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

## What is not here

- **No rules content.** No levels, no stat blocks, no encounter budgets, no dice.
- **No maps or coordinates.** Places relate through containment (`parent_id`) and trade
  (`travel`), not geometry.
- **No incremental sync.** Every export is a full snapshot; diff against your last copy by
  `id` if you need to know what changed.
