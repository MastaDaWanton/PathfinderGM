# Campaign export format

**Schema version 1.5.** Read this before writing anything that consumes a World Bible
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
{ "schema_version": "1.5" }
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
| `settlements` | `{id, name, scale, sells, buys, tension, governed_by, parent_id}`. *(proposed, read today)* `landforms`: `[{name, terrain, miles, words}]`, two to four named stretches of open ground within a short walk (a `crosses` terrain word, miles from the settlement's edge, the world's own clause). Given, it is the settlement's hinterland exactly; absent, the consumer derives one from the routes and the region's prose (docs/from-world-bible.md). |
| `cast` | `{id, name, role, home_id, home}` |
| `travel` | `{from_id, to_id, from, to, carrying, friction, by}` — a route is also a road between two places that demonstrably deal with each other. *(1.5)* `by` is `road`, `sea` or `river`, and it **outranks anything a consumer can work out**: a trade route is an economic relationship, and "Brackgate sells tempered steel to Ashwatch" was never a claim that you can walk there. Measured before it existed: 48 of Aurvantis's 48 legs crossed a continent boundary and every one of them was being walked. Aurvantis 1.5 says road 81, sea 38, river 13. |
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
  "weakness":  "nimble",
  "grants":    ["move.fly.30", "sense.blindsense.30", "natural.claws"]
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
- *(1.5)* `grants[]` is the card's own list of tags, and **when it is present nothing is
  read out of the prose** — not a trait, not a sense, not a natural weapon. The exact
  names are in `docs/race-cues.json` under `grants`. This is the field that matters most
  on a modern card: everything above it is description, and the description should be
  written *from* these tags rather than the tags guessed from it. A tag the consumer does
  not know reaches nothing and is shown to the player as a trait neither side can name.

  Ruled 2026-09-16: *"we should not need to interpret anatomy on import. We should
  receive exactly the anatomy as our engine will read it, and World Bible should also
  write the description from those tags."* What that replaced, measured the same day on
  the shipped Aurvantis export: a Half-Orc card reading "sometimes visible tusks" tripped
  a `tusks?` pattern here and put a 1d6 bite on every half-orc a player could roll.

  Note what the defect is and is not. It is not that half-orcs should not bite — these
  are **this world's** peoples, and an Aurvantis orc is Aurvantis's whatever the Bestiary
  says about the name. It is that nobody chose. Under prose-reading the world could not
  DECLINE the bite without deleting the word "tusks" from a sentence about their faces,
  and a rule nobody can decline is a rule nobody selected.
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
| `kind` | *optional* — what the place IS when its name does not say: one of the consumer's settlement kinds (`docs/place-vocabulary.json`, the `settlement_places` names without "the"), or a word folded to one ("forge" → `smithy`, "alchemist's lab" → `laboratory`). Read since 2026-10-06 (the alchemy revamp; see "Alchemy" below): "the Glasshouse" with `"kind": "laboratory"` is a laboratory, kept by an alchemist, and its city gets no second one appended. A kind the consumer does not know is dropped and the name reads as before |
| `keeper` | *optional* — `{"name": str, "known": "publicly"}` for a keeper everybody knows by name (the name over the shop). Without `known: "publicly"` the consumer keeps the name back until it is given in play, as it does for every keeper it mints (owner ruling F1, 2026-09-30; `keepers.publicly_known`). A `play.cast[]` row may say the same with `"keeps": "<place id>", "known": "publicly"` |

All five of the tier-2 fields are **read** as of 2026-09-16 (`rules/floorplan.from_world`,
`rules/places._authored`): the dimensions become the grid a fight is laid out on at five
feet to a square, `clutter` and `footing` become what is in the way and what is hard going,
`vertical` is used as written, and `storeys` is the floors themselves. Nothing about a plan
is saved — an authored place is re-read from the export every time, which is why changing
these fields and re-exporting changes the ground under an existing campaign.

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

### `play.flora[]` (proposed: no export carries it yet, and it has no version number)

A world's own herbs, fungi and the parts of its own creatures, for the herbalist's bench.
Until an export carries them the app uses its shipped corpus,
`content/ingredients/herbs-and-parts.json`, whose rows already have this shape. Written
down now (2026-10-02, the herbalism revamp) so that the fields the bench reads are the
fields a world would send, and a world's flora is never validated against the shipped herb
it shares a name with (the owner's ruling on races: a world's peoples are its own even
when one is called Orc, and the same holds for its plants).

**Every field below is optional, and the default is what the app assumes when it is
absent.** All of them are words or flags, never rules numbers: how strong a neutralizer is
is an ordinal, and the app turns words into DCs and dice itself.

```json
{
  "id": "5bbd0c40345f~flora:ashleaf",
  "name": "Ashleaf",
  "about": "A grey creeper on burned ground; chewed, it numbs a toothache.",
  "kind": "herb",
  "grows_in": ["forest", "hills"],
  "rarity": "common",
  "part": "leaf",
  "uses": [{"text": "Chewed, it numbs a toothache.", "route": "ingest"}],
  "base_for": [],
  "solvent": "",
  "neutralizer": 0,
  "hybrid": false
}
```

| Field | Meaning | Default |
|---|---|---|
| `kind` | `herb`, `fungus`, `monster part`, `poison` | `herb` |
| `part` | what of it is used: `leaf`, `flower`, `root`, `bark`, `berry`, `seed`, `sap`, `resin`, `fungus`, `gland`, `organ`, `bone`, `horn`, `feather`, `scale`, `eye`, `shell`, `oil`, `wax`, `mineral`, `liquid` | `leaf` for a herb or poison, `organ` for a monster part, `fungus` for a fungus |
| `uses[].route` | how one use reaches a body: `ingest`, `skin`, `eyes`, `wound`, `inhale`, or `external` for a use that reaches outside the body or changes what others perceive (light, invisibility, a cloud over an area, a coating on a blade) | `ingest` |
| `base_for` | what it thickens: any of `salve`, `balm`, `cream`. Ground bark and tree sap or resin are salve bases | `[]` |
| `solvent` | a carrier it serves as: `oil`, `alcohol`, `vinegar`, `water` | `""` |
| `neutralizer` | how strongly it quiets a volatile ingredient: `0` none, `1` mild, `2` strong. `true` reads as `1` | `0` |
| `hybrid` | `true` when any use is magical (planar flora, a creature's supernatural part); it then also appears on the alchemist's shelf | `false` |

The app reads these into `rules/ingredients.Ingredient`, whose `from_dict` applies the same
defaults, so a world that sends only `name` and `about` still loads.

## Materials

### `play.materials[]` (proposed: no export carries it yet, and it has no version number)

A world's own metals, alloys, fittings and forge reagents, for the smith's bench — and the
same list carries every other craft's materials, an alchemist's reagents among them (see
"Alchemy" below: one material, many shelves, the shelf decided by `kind`). Until an
export carries them the app uses its shipped shelf, `content/materials/*.json`, read through
the one door `rules/materials.py`, whose rows already have this shape. Written down
2026-10-04 (the blacksmithing revamp, plan §15.1) under the standing instruction that fixes
are world-agnostic: a world's local metal goes through the same build as the shipped iron,
and can stand in for iron or silver with numbers of its own. As with races and flora, a
world's metal is its own even when it is called Mithral; it is never validated against the
shipped material it shares a name with.

**Every field below is optional, and the default is what the app assumes when it is
absent** (`materials.normalise` applies them, so a row with only `id`, `name`, `kind` and
`text` loads and is simply inert at the forge). The numbers in `weapon`, `armour` and
`quench_mark` are the one place in `play` that carries rules-shaped values, and they are
held to the same fences the shipped data is (`materials.validate`, with the fix named):
house modifiers start at ±2 and stay within the tier's ceiling (common and uncommon ±2,
rare and exotic ±3, legendary ±4), every structural list has at least three effects and
at least one drawback, nothing is `narrative`, and every material has at least three
things to discover. A row that fails is reported, not guessed at.

```json
{
  "id": "5bbd0c40345f~material:dusk-iron",
  "name": "Dusk Iron",
  "kind": "metal",
  "tier": "uncommon",
  "text": "A blue-black iron smelted in the eastern hills; it takes an edge and keeps it.",
  "pieces": {"weapon": ["head", "fittings"], "armour": ["body", "fastenings"]},
  "weapon": [
    {"type": "combat_mod", "target": "damage", "amount": 2, "bonus_type": "material"},
    {"type": "combat_mod", "target": "attack", "amount": -2, "bonus_type": "material"},
    {"type": "gear_mod", "target": "hardness", "amount": 2}
  ],
  "armour": [
    {"type": "combat_mod", "target": "ac", "amount": 2, "bonus_type": "material"},
    {"type": "gear_mod", "target": "acp", "amount": -2},
    {"type": "gear_mod", "target": "hardness", "amount": 2}
  ],
  "working": [{"type": "working", "trait": "forgiving"}],
  "forms": ["ore:dusk-iron-ore", "ingot", "bar"]
}
```

| Field | Meaning | Default |
|---|---|---|
| `kind` | the forge's kinds: `ore`, `metal`, `alloy`, `fuel`, `flux`, `quenchant`, `fitting`, `treatment`; the other crafts' (`essence`, `focus`, `ink`, `chalk`, `catalyst`, `solvent`, `tannin`, `oil`, `wax`, `thread`...); and the substances a piece can be made of, `hide`, `leather`, `wood`, `bone`, `horn`, `cloth`, `stone`, `glass`. **`kind` is what the material tag reads** (see "What the material tag reads" below): `metal` and `alloy` are metal, `hide` and `leather` leather, `thread` cord, the rest themselves | `metal` |
| `tier` | `common`, `uncommon`, `rare`, `exotic`, `legendary`: what the bench may work and the ceiling on any one house number | `common` |
| `form` | the shelf it sits on: `ore`, `bar`, `alloy bar`, `haft`, `grip`, `guard`, `fuel`, `flux`, `quenchant`, `treatment`... | read from `kind` (a fitting's from its id) |
| `material` | the id of the material this is a FORM of ("mithral fittings" is mithral; an ore points at its metal), so a prospected ore and a bought bar are one material. **Required on a `fitting`** (and on any row whose `kind` is not a substance): a fitting's kind says only "fitting", and the material tag follows this link to learn what it is made of; without it the fitting is made of nothing the tag can name | its own id |
| `enchant_surcharge_gp` | what enchanting an item made of it costs extra, once, the first time it is enchanted (the book's cold iron +2,000 gp on a weapon's main piece; noqual's +5,000 on any piece). The book's own materials only: a world's metal that should resist magic says so here, in gold, and the app turns it into motes | `0`: no surcharge |
| `pieces` | which piece slots it fills, per gear: weapon `head`, `haft`, `fittings`; armour (and shield) `body`, `fastenings`, `lining`. The head and body count in full, every other piece at half | `{"weapon": [], "armour": []}`: fills nothing |
| `weapon` | the effects it brings to a weapon, in the effect vocabulary (`rules/effectspec.py`): `combat_mod`, `gear_mod` (`acp`, `max_dex`, `asf`, `weight_pct`, `hardness`, `hp_per_inch`, `category`, `speed_penalty`), `strikes_as` (`cold_iron`, `silver`, `adamantine`, `ghost_touch`), riders with a `trigger` (`hit`, `crit`, `first_wound_daily`, `carried`) and conditions in `when` (`target`, `attacker`, `armour`, `weapon`, `against`) | `[]` |
| `armour` | the same, for a suit or a shield (a forged shield reads the `armour` list) | `[]` |
| `working` | how it behaves at the anvil: `{"type": "working", "trait": ...}` with a trait from `effectspec.WORKING_TRAITS` (`forgiving`, `slaggy`, `narrow_window`, `reactive`...). Never reaches the finished item | `[]` |
| `quench_mark` | quenchants only: the one small effect it leaves on what it hardens | `null` |
| `book` | `true` when the row carries printed PF1e numbers, each such effect marked `"book": true`; those come from the main piece only and are never scaled. A book row's `price_gp` is the book's too, and the price rule does not hold it to the house rungs (cold iron is cheaper than copper by the book; the enchanter's masterwork vessels are the Core Rulebook's +300/+150 gp surcharges). A world's own metal is house, not book | `false` |
| `forms` | the chain of shelves it passes through (`"ore:<id>"`, `ingot`, `bar`, `blank`, `plate`) | computed from `kind` and from the rows that name it as their `material` |
| `feeds` | for a metal with no piece to fill, which forge methods it is stock for (`alloy`, `smelt`) | `[]` |
| `finishes` | treatments only: which gear it can be laid over (`weapon`, `armour`) | `[]` |
| `not_on` | treatments only: material ids it may not be laid over (the book's alchemical silver is never put on adamantine, cold iron or mithral) | `[]` |
| `assay_danger` | reactive metals only: what handling a sliver does to the assayer when its harm is not a carried effect. One type today, `suppress_magic` (noqual's, a house rule), with a `duration` and `"house": true` or `"book": true` | `null`: an assay is safe |
| `price_gp`, `biomes`, `obtain` | what it costs at a market, where it is found, how (`mined`, `bought`, `harvested`). **Required on a common `fuel`, `flux` or `quenchant`**: those are staples on every counter that sells the smith's supplies (`content/rules/stall-lines.json` `consumables`, 2026-10-05), and an unpriced one would be on none. **Held to the price rule** (`rules/pricing.py`, `material_price_problems`, 2026-10-05): at least the rung's floor (common 1, uncommon 5, rare 25, exotic 125, legendary 625 gp), ×5 for an `essence`, `catalyst`, `ink`, `chalk`, `focus` or a row with `neutralizer`, × how far its `plus`, `capacity`, `neutralizer` or `dc_mod` runs above its rung; never cheaper than a commoner row of its kind in its file, and a stronger row costs strictly more than a weaker one. 1 cp is the "free" token, allowed only on a plain common row (water). Absent stays absent: an unpriced row is simply not sold | none, `[]`, `""` |

### What the material tag reads (2026-10-05: the enchanting revamp, lane B)

Spells that affect metal (heat metal, chill metal, shocking grasp against metal armour), the
druid's no-metal rule and the enchanter's surcharges all ask one question of an item —
*is it metal, and which metal* — through one set of tags: `material.metal`,
`material.metal.<id>`, `material.main.<id>` (`rules/item_tags.py`). The answer is read
from data, never from a name ("ironwood" is wood, "silver-clasps" are metal):

1. the row's own `kind`, mapped to a substance by `content/rules/base-pieces.json`
   `kinds` (`metal`, `alloy` → metal; `hide`, `leather` → leather; `thread` → cord; `wood`,
   `bone`, `horn`, `cloth`, `stone`, `glass` as themselves);
2. otherwise its `material` link, followed to the root (a world's "guild fittings" pointing
   at `brass` are metal because brass is).

So a world's own metal is metal the day it is exported with `kind: "metal"`, and a world's
fitting must carry `material`. A row with neither answers nothing: it is never guessed.

### A world's essences (proposed, 2026-10-05: the enchanting revamp, lane D)

A `play.materials[]` row with `kind` `essence` is a thing an enchanter binds, read through
the same door (`materials.essences()`) and held to the same fences as the shipped shelf
(`materials.essence_problems`, every refusal with its fix named). Nothing in it is
world-specific except the words: the numbers are the app's rules. Ids are forever: an item
bound with an essence names it by id on its layer (`magic.properties[].essence`), and the
essence's `house` top-ups are read live from that id, so a renamed id orphans the top-ups of
every item that carries it.

| Field | Meaning | Default |
|---|---|---|
| `grants` | what it binds: `{"property": id}` from `content/rules/magic-properties.json` (with an optional `choice`, `{"energy": "fire"}`, or `bonus` for a scaled one), `{"enhancement": n}` (1 to 5), or absent for an essence that is only potency | absent: a mote supply |
| `motes` | potency, the cost unit: 1 mote = 100 gp of the book's making cost. At least what its grant costs to make (`materials.grant_motes`); a sold essence exactly that | required |
| `tier` | **not free**: the band of the market value its motes carry (motes × 200 gp: under 1,000 common, 5,000 uncommon, 20,000 rare, 50,000 exotic, then legendary). World Bible computes it, never chooses it | required |
| `price_gp` | motes × 100 when `obtain` is `bought`; absent otherwise (a found essence is not sold) | absent |
| `family` | the family it belongs to: one of the shipped families (`fire`, `cold`, `holy`, `shadow`... the `families` table in `enchanter-materials.json`) or the world's own | required |
| `phase` | the phase of the day its family favours, one of `dawn`, `morning`, `noon`, `afternoon`, `dusk`, `night`, `midnight` (`rules/sky.py`). Never a planet: a world need have none. Taken from the family when the family is a shipped one; **required for a family of the world's own** | the family's |
| `polarity` | where it wants to sit: `weapon`, `armour`, `ward` (rings, cloaks, belts), `any` | required |
| `affinity` | material ids (the world's or the shipped) that suit it | `[]` |
| `house` | at least one small typed top-up, each `"house": true`, inside the tier's ceiling (common and uncommon ±1, rare and exotic ±2, legendary ±3); never `narrative`, never one of the magic-item types still waiting on a reader | required |
| `working` | the circle's traits: `night_only`, `eager`, `skittish`, `heavy`, `volatile` (needs a drawback in `house`), `pure` | `[]` |
| `color` | `#rrggbb`, the glow on the binding stage | required |

A world's essence harvested from its own creature names the creature in `from_creature`,
in the world's words, or — better, and read first — the creature carries the tag
`harvest.essence.<material-id>` in its own `tags`. The reader is built (2026-10-06,
`rules/gathering.py` `harvest_tagged`, every carcass excursion): one grammar for every craft,
`harvest.<branch>.<material-id>` with branches `hide`, `horn`, `bone`, `sinew`, `scales`
(leatherworking), `blood` (the forge), `reagent` (alchemy), `essence` (enchanting) and `part`
(herbalism). A tag naming no material on that craft's shelf is ignored, never invented into
one; a creature with no harvest tags is matched by `from_creature(s)` as before.

What a world never sends for enchanting: **a sky.** The favourable time is the essence
family's phase of the day (owner, round 4 point 10: "this is not earth", named planets
would not be world-agnostic), computed from the game clock with dawn at 06:00 and dusk at
18:00 (`rules/sky.py`). No planets, no day length, no calendar of stars.

### `play.magic_items[]` (proposed, 2026-10-06: the enchanting revamp, lane H; no reader yet)

A world's own named magic item — the Wardens' Blade, the ring every Vormoor reeve wears — is
a thing someone owns or a hoard holds, not a recipe. It is shaped exactly as the app stores
an enchanted item, so the reader, when it is written, is `forge_items.record_for_base` plus
the layer it already reads (`rules/magic_layer.py`): **ids and choices only, never a
number.** What the item does, its price, its aura and its caster level are computed from the
app's property table and recipes on every read, so a world cannot ship a +3 sword that hits
like a +5.

```json
{
  "id": "5bbd0c40345f~item:wardens-blade",
  "name": "The Wardens' Blade",
  "text": "Carried by every Warden-Captain of the Ashfold march since the burning.",
  "base": "longsword",
  "gear": "weapon",
  "pieces": {"head": "5bbd0c40345f~material:dusk-iron"},
  "magic": {
    "enhancement": 1,
    "properties": [{"id": "bane", "choice": {"foe": "undead"}},
                   {"id": "flaming"}],
    "powers": [],
    "curse": null
  },
  "owner_id": "5bbd0c40345f~character:ysolde-marr"
}
```

| Field | Meaning | Default |
|---|---|---|
| `base` | a weapon, armour or shield from the app's tables (`longsword`, `chain shirt`, `heavy steel shield`), or for a ring or wondrous item its slot (`ring`, `shoulders`, `neck`...) | required |
| `gear` | `weapon`, `armour`, `shield`, `ring` or `wondrous` | read from `base` |
| `pieces` | which material fills which piece (`head`, `haft`, `fittings`; `body`, `fastenings`, `lining`), the world's own `play.materials[]` ids or the shipped ones. A piece not named is the base's default (`content/rules/base-pieces.json`) | the defaults |
| `magic.enhancement` | the +N, 1 to 5, arms and armour only (the book's limit, kept) | `0` |
| `magic.properties[]` | `{"id": <content/rules/magic-properties.json id>, "choice": {...}}`. **A property that asks a choice must carry it** (bane's `foe`: a creature type, or `{"subtype": "<the world's own subtype>"}` for a humanoid or outsider; resistance's `energy`; skill competence's `skill` and `bonus`): an item that never named its foe is the very defect the app's old saves had, and the app would have to ask the player | `[]` |
| `magic.powers[]` | `{"recipe": <a wondrous recipe id>}` from `content/materials/magic-items.json` | `[]` |
| `magic.curse` | a curse from the book's table, `{"row": <content/rules/curses.json row>, ...}`, hidden until identified | `null` |
| `owner_id` / `where_id` | who has it, or the place it lies in | absent: nowhere yet |

A world's own *kind* of magic — a property the book does not print — is not expressible
here, on purpose: what an enchantment does is the book's (the owner's round 2, "every book
property works"), and the world chooses which of them its items carry and in what words.

**Who sells a craft's supplies** (proposed, no reader yet). A `play.places[]` row may carry
`"supplies": ["blacksmith"]` — the crafts whose consumables (fuel, flux, quench; solvents,
salts, vials; bark, oil, wax, thread; ink, chalk, seal) its keeper always has, from
`blacksmith`, `alchemist`, `leatherworker`, `enchanter`. Words only; the prices are the
materials' own. Absent means the app's own table decides by the place's kind (the smithy,
the tannery, the workshops); `[]` means the keeper sells none. Which materials a craft
consumes is the app's (`consumables.kinds`), read off each row's `kind`, never its name.

The app reads these through `rules/materials.py`; the forge's item build
(`rules/forge_items.py`) computes everything else on read — a record of a forged item
stores which material went into each piece, never a number.

## Alchemy

Written 2026-10-07 by the alchemy revamp's lane I (docs/alchemy-revamp-plan.md §19), which
folds in what lanes A to H found. Nothing here is a new export section: a world's alchemy
arrives through the rows it already has — `play.materials[]` for its reagents, `play.flora[]`
for its hybrid herbs, `play.places[]` for its laboratories, `play.cast[]` for its alchemists.
Fixes are world-agnostic (the standing instruction of 2026-09-28), so every field below is
what the shipped shelf itself is written in: `content/materials/alchemist-materials.json`
(139 rows: reagent 46, gland 22, solvent 16, vessel 14, salt 11, treatment 11, essence 10,
catalyst 9) and the 63 hybrid herbs of `content/ingredients/herbs-and-parts.json`. As with
races, flora and metals, a world's reagent is its own even when it is called Brimstone; it
is never validated against the shipped row it shares a name with.

### A world's reagents: `play.materials[]` rows of an alchemist's kind

`play.materials[]` (above) is one list for every craft: **one material, many shelves** (the
owner's Q2.1). A row is on the alchemist's shelf when its `kind` is one of the alchemist's
eight — `reagent`, `gland`, `solvent`, `vessel`, `salt`, `catalyst` (only the alchemist's),
`treatment` and `essence` (shared with the forge and the enchanter, so a row of those two
kinds says which by carrying `product`) — or when it writes `product` at all. No `shelves`
field is read: the plan proposed one, and `kind` already answers the question (`materials.
is_alchemy`).

```json
{
  "id": "5bbd0c40345f~material:fen-sulphur",
  "name": "Fen sulphur",
  "kind": "reagent",
  "tier": "common",
  "text": "Yellow crust off the marsh vents; it burns with a choking blue flame.",
  "product": [
    {"type": "damage", "dice": "1d4", "damage_type": "fire", "route": "struck",
     "essence": "fire", "grade": 1},
    {"type": "apply_condition", "target": "sickened", "duration": {"amount": 1, "unit": "round"},
     "route": "ingest", "essence": "decay", "drawback": true}
  ],
  "working": [{"type": "working", "trait": "solid"}, {"type": "working", "trait": "volatile"}],
  "mishap": {"type": "damage", "dice": "1d4", "damage_type": "fire", "recipient": "self",
             "note": "the charge flashes in the crucible"},
  "toxic": null,
  "color": [0.86, 0.78, 0.22],
  "biomes": ["marsh"], "obtain": "gathered", "price_gp": 1
}
```

| Field | Meaning | Default |
|---|---|---|
| `product[]` | what it puts into a bottle: effect documents in the app's vocabulary (`rules/effectspec.py`), each with an **`essence`** (one of the eighteen below), a **`route`** (below), a `grade` (1 and up; same-named traits from two materials add their grades at the bench, capped by the Alchemist level) and `drawback: true` on a cost. Never `narrative`: the validator refuses it with the fix named | `[]`: the row brings nothing to a bottle and must then have a job at the bench (a solvent, a vessel, a catalyst) |
| `working[]` | how it behaves at the bench, `{"type": "working", "trait": ...}`: `solid`, `liquid`, `volatile`, `stabilizer`, `catalyst`, `apparatus`, `combustible`, `slow_to_dissolve`, `light_sensitive`, `corrosive`, `toxic_to_handle`, `wild`, `fireproof`, `warded`, `lead_lined`, `solvent:<water\|alcohol\|vinegar\|oil\|acid>`, and the vessel traits that decide a product's family — `drinkable` (potion or oil), `shatters` and `bursts` (a thrown splash flask), `struck` (a cloud), `stick` (a tool) | `[]` |
| `mishap` | `volatile` only, and required with it: one effect document (with `"recipient": "self"`) that lands on the alchemist when a step with it fails by 5 or more, stated before the roll | `null` |
| `toxic` | `toxic_to_handle` only, and required with it: what working it unprotected does to the alchemist | `null` |
| `color` | `[r, g, b]`, 0 to 1: the liquid colour on the bench's glassware, mixed by amount | none: the stage shows a neutral glass |
| `form` | its own form word when its `kind` does not say it (`powder`, `liquid`) | its `kind` |
| `material` | the id of the material this is a form of, as the forge's rows (a world's "red sulphur" naming `brimstone`) | its own id |
| `tier`, `text`, `biomes`, `obtain`, `obtain_dc`, `from_creature(s)`, `price_gp` | as every `play.materials[]` row. `tier` gates the bench (common and uncommon at Alchemist 1, rare and exotic at 2 and in a laboratory, legendary at 3); `obtain` and `biomes` send the alchemist's quarry, gathering and harvest excursions for it (`content/rules/gathering.json`; a `salt` or `reagent` comes to the alchemist's quarry in full batches and to the smith's prospect at half); `price_gp` is held to the one price rule (×5 for an `essence` or `catalyst`) | as above |
| `craft_dc`, `book` | a book reagent's printed numbers; a world's own row leaves both out | `null`, `false` |

**The fences a world's row is held to** (`materials.validate`, the alchemy branch; each
refusal names its fix): at least three discoverable properties across `product`, `working`,
`mishap` and `toxic`; at least one drawback when it has product traits; every product trait
with an `essence` and a `route`; house numbers inside the tier's ceiling (plan §5.6); a
`volatile` row has a `mishap` and only a volatile one does; a `toxic_to_handle` row has a
`toxic` document and only such a one does. The shipped shelf is pinned clean against the
same validator by test (`tests/test_alchemy_materials.py`); the day `play.materials[]` has a
reader, a world's row that fails must be reported with those words, never repaired by guess.

**The eighteen essences** (`effectspec.ESSENCES`, kept by the owner on 2026-10-06): `fire`,
`frost`, `acid`, `storm` (electricity), `thunder` (sonic), `light`, `shadow`, `vigour`
(healing), `purity` (ending conditions, poison, disease), `ward` (resistance, saves, AC),
`might` (Str, Con, attack, damage), `grace` (Dex, land speed), `mind` (Int, Wis, Cha,
emotion), `lightness` (flight, climbing, falling softly), `sight` (senses, divination),
`binding` (entangling, gluing, holding), `decay` (poison, sickness, necromancy), `change`
(form, size, substance). A world never adds one: formulae key on these ids, and an essence
no formula asks is a reagent nothing can be made of.

**Routes** — how a trait reaches whoever it reaches: the herb's six (`ingest`, `skin`,
`eyes`, `wound`, `inhale`, `external`) and the alchemist's four (`struck`, what a thrown
flask does to the creature it hits; `splash`, everyone within 5 ft of where it lands;
`area`, everyone inside a cloud; `carried`, a cost on whoever carries the product). A
product's family (potion, oil, splash flask, cloud, tool) carries only the routes it can
deliver; a trait that cannot travel is shown dimmed with its reason at the bench and left out.

### A world's hybrid herbs: `play.flora[]`

`hybrid: true` puts a herb on the alchemist's shelf as well as the herbalist's, one document
on two shelves; its `external` uses are the alchemist's own (the herb bench drops them). Each
use may name an **`essence`** (`uses[].essence`, one of the eighteen): without one it is a
herb to the alchemist but makes no formula. Every one of the 201 shipped hybrid herb effects
carries one. A herb's id and a material's id must never be the same: `basilisk-eye` was both
until the alchemy revamp merged the gland into the herb, and one knowledge entry stood for
two documents (`tests/test_alchemy_shelf.py` now pins every material id against every
ingredient id).

### Formulae are not exported

What a mix can become is a fixed, world-agnostic table (the owner's Q5.2: "never secret per
world"): the sixteen book classics and the 44 authored spell potions in
`content/rules/alchemy-formulae.json`, and one derived row for every corpus spell whose
effects all run (425 today, `rules/formulae.py`). A world feeds it two ways only: its
reagents carry essences, and its spells (if it ever exports any) join the spell corpus. A
world that sends a recipe list is sending something the app will not read.

### Laboratories and alchemists

| Field | Meaning |
|---|---|
| `play.places[].kind: "laboratory"` | read since 2026-10-06 (the places row's `kind`, above): a world's own laboratory by any name ("the Glasshouse") is one, its keeper an alchemist, and its city gets no second one appended. Every city the world does not give one has "the laboratory" appended (the owner: "every city has a laboratory to rent"); a town or village has one only when its own words name its alchemists or play founds one |
| `play.cast[]` alchemists | words only: a person described as "an alchemist" or "a chymist" is one (the app's occupation `alchemist`, tag `alchemy`, `content/people/occupations.json`). A world's own word for the trade needs that table to learn it |
| prices | none from a world. A town laboratory rents at 2 sp an hour (`market.LAB_RENT_CP_PER_HOUR`, a house rate; the book only sells a lab outright, 200 gp); the party's own costs nothing. Products sell at the book's price (a spell potion 50 gp × spell level × caster level), the tier ladder for a house compound, the quality ladder multiplying both; reagents at their own `price_gp` |

## Leatherworking

Written 2026-10-08 by the leatherworking revamp's lane W (docs/leatherworking-revamp-plan.md
§21; contracts §11), from what lanes A to I built. As with alchemy, nothing here is a new
export section except one field on creatures: a world's leatherwork arrives through the rows
it already has, `play.materials[]` for its hides and the tannery's consumables,
`play.places[]` for its tanneries, `play.cast[]` for its tanners. Fixes are world-agnostic
(the standing instruction of 2026-09-28), so every field below is what the shipped shelf
itself is written in: `content/materials/leatherworker-materials.json` (140 rows: hide 77,
including the six generic hides, tannin 14, dye 12, thread 11, fitting 9, oil 8, wax 5,
treatment 4). A world's hide is its own even when it is called Wolf Pelt; it is never
validated against the shipped row it shares a name with.

### A world's hides: `play.materials[]` rows of `kind` `hide`

A hide is a structural material, like a metal (contracts §3): it fills the **body** of a
suit, a shield or a worn good, and the forge's build (`forge_items.build`) sums its numbers
exactly as it sums a metal's. Leather armour is the forge's armour model (owner Q7.1), so a
world's hide meets the same fences a world's metal does (`materials.validate`, every refusal
with its fix named).

```json
{
  "id": "5bbd0c40345f~material:marsh-elk-hide",
  "name": "Marsh Elk Hide",
  "kind": "hide",
  "tier": "common",
  "text": "Heavy and close-haired; the fen people say it never quite dries.",
  "surface": "fur",
  "color": "#7a5a3c",
  "size": "large",
  "fresh_hours": 48,
  "sold_as": "fur",
  "price_gp": 2,
  "creature_type": "animal",
  "pieces": {"armour": ["body", "fastenings", "lining"], "shield": ["body"],
             "worn": ["body", "lining"]},
  "armour": [
    {"type": "resistance", "target": "cold", "amount": 2},
    {"type": "skill_mod", "target": "survival", "amount": 2, "bonus_type": "material"},
    {"type": "gear_mod", "target": "acp", "amount": -2}
  ],
  "working": [{"type": "working", "trait": "thick"}, {"type": "working", "trait": "slow_tan"}]
}
```

| Field | Meaning | Default |
|---|---|---|
| `pieces` | which slots it fills, per gear: `armour` (`body`, `fastenings` as a lacing set, `lining`), `shield` (`body`: the madu), `worn` (`body`, `lining`: cloaks, boots, gloves, bracers, belts, caps, satchels, quivers), and `weapon` `haft` **only for a grip-capable hide** (sharkskin, dragonhide: the grip the forge's Assemble takes, owner Q7.4) | fills nothing |
| `armour` | **at least three effects, at least one a drawback** (owner Q3.1), in the effect vocabulary. Read for a suit, a worn good (less its `ac`, `acp`, `max_dex` and `asf`: a cloak has no armour bonus to change) and a shield when `shield` is empty. A hide's AC is typed `material` and folds into the suit's armour bonus; typed `armour` it would be swallowed by the suit's own (measured: 13 shipped hide specs did nothing, inventory §0.2). Never `narrative` | `[]` |
| `shield` | a shield's own list when it should differ from `armour` | reads `armour` |
| `weapon` | only on a grip-capable hide, then at least three, at least one a drawback. A `weapon` list on any other hide is refused | `[]` |
| `working` | at least one trait from the leather list (`effectspec.WORKING_TRAITS`): `thick` (it can make hide armour), `fast_tan`, `slow_tan`, `ceiling_up`, `ceiling_down`, `salt_proof`, `tans_white`, `supple`, `fills_tooling`, `strong_seam`, `weatherproof`, `fine_pitch`, `fast_colour`, `fugitive`, `rancid`, besides the forge's own | `[]` |
| `surface` | `fur`, `scale`, `smooth`, `feather`, `chitin`, `shell`: what the bench and its stage draw, and which generic hide a creature with no named hide gives (below) | `smooth` |
| `color` | `#rrggbb`, the swatch on the rack and the hide on the stage | the kind's colour |
| `size` | the hide's size, `tiny` to `colossal`: its **hide units** (Medium 1, doubling per size, plan §5.5) when it is bought or converted, so a Large hide is two units and cuts a Medium suit's body. Lane E measured 2026-10-08 that the one door dropped this field, and every Large hide read as one Medium unit | `medium` |
| `fresh_hours` | how long it keeps green, from the minute it comes off the carcass, before it spoils to scraps: 48 on every shipped hide (owner Q4.4), the herbalist's animal clock. Salt stops it for six weeks; tanned leather never spoils | 48 |
| `sold_as` | the form a counter sells it in: `leather`, `fur` or `rawhide`, never green (a green hide "cannot be bought or sold in most settlements", plan §9). Must be one of its forms. A bought hide is oak-bark tanned at grade 2 (lanes D and E, for the owner's review) | `fur` for a fur or feather surface, else `leather` |
| `price_gp` | the price of that sold form, held to the one price rule (`rules/pricing.py`: common 1, uncommon 5, rare 25, exotic 125, legendary 625 gp at least). **Required on a common hide** to be on the leatherworker's counter: every settlement's leatherworker always stocks the common hides and dyes that carry one (owner, 2026-10-08, open point 9; `stall-lines.json` `staple_kinds`), and an unpriced one is on no counter (measured: 15 of the 21 shipped common hides are priced) | absent: not sold |
| `creature_type` | the creature type it comes from, in the bestiary's spelling (`animal`, `magical-beast`, `dragon`, `outsider`, `vermin`...): Grade (the leather assay) is one easier for each known hide of the same type, at most four (plan §16, lane F). Stated on the hide because names do not resolve: the bestiary finds only 45 of the 71 shipped named hides' creatures, no dragon among them | none: no comparison |
| `allowed_bases` | the table suits it may be made into, when the book limits it (angelskin: leather, hide armour, studded leather) | any |
| `always_masterwork`, `book` | the book's masterwork-by-nature hides (dragonhide, eel hide, angelskin, darkleaf), with their printed effects marked `"book": true`. A world's own hide is house, not book | `false` |
| `druid_permitted` | a hide armour a druid may wear with no penalty although it is armour (the book's own few) | `false` |
| `from_creatures` | creature names, the old fallback for a carcass with no harvest tags. Prefer the tags (below); a name never decides when a tag exists | `[]` |
| `material` | as every row: the hide this is a form of | its own id |

### The tannery's consumables: tannins, oils, waxes, threads, dyes, fittings, treatments

Rows of `kind` `tannin`, `oil`, `wax`, `thread`, `dye`, `fitting` or `treatment`. They bring
**working traits only**, never an `armour` or `weapon` list (owner Q3.2: a tannin's prose
reached the finished item before the revamp, "a boar-hide suit listed 'the standard tanning
agent'"), at most one small `mark`, and **marks are on hold** (owner, 2026-10-08: an
explanation was asked for before deciding), so a world sends none until the app says.

| Field | Meaning | Default |
|---|---|---|
| `tannage` | **required on a tannin**: how it tans, one of `brain`, `alum`, `bark`, `mineral`, `planar` (plan §8.1). It decides the time in the vat, whether the leather can be hardened (not alum or brain) and where the work can be done | none: a row without one is refused |
| `salt` | `true` on a treatment that cures a hide (the shipped `curing-salt`): what the harvest spends, one measure per hide unit, to stop a hide's clock, and what herbalism's animal parts use too. Read by id and kind, never by a name fragment | `false` |
| `material` | **required on a fitting** (the forge's rule): the root metal, so steel studs answer the metal tag and a druid's armour check reads them (`"material": "steel"`) | its own id |
| `price_gp` | the one price rule. **Required on every common consumable** and every common dye: the leatherworker's counter carries them always, never sold out, and only priced rows reach it | absent: not sold |

### Creatures carry their own harvest (the owner's rule)

The owner, 2026-10-05 (Q9.2): "apply the tags to the beasts and just have a reader in
skinning to find the relevant tag with that no list is necessary." So there is **no fauna
list**. A creature says what its carcass gives in its own `tags`, in the one tag vocabulary,
and the harvest's reader finds them; it reads **only tags and stat-block fields**, never the
creature's name (a wolf the narrator calls "the grey one" still yields its pelt).

| Tag | Means |
|---|---|
| `harvest.hide.<material-id>` | this beast yields that named hide |
| `harvest.hide.generic.<surface>` | a generic hide of this surface (`fur`, `scale`, `smooth`, `feather`, `chitin`, `shell`): the shipped `generic-fur-hide` and its five siblings, made the beast's own by its stat block (below) |
| `harvest.horn.<id>`, `harvest.bone.<id>`, `harvest.sinew` | the outer parts a leatherworker takes |
| `harvest.scales.<id>` | the best scales, for the forge's dragon-scale suits |
| `harvest.plan.<plan>` | the body plan the bench's 3D hide is drawn from: `quadruped`, `long`, `winged`, `serpent`, `carapace`. Drawing only |
| `harvest.blood.<id>`, `harvest.reagent.<id>`, `harvest.essence.<id>`, `harvest.part.<id>` | the forge's, the alchemist's, the enchanter's and the herbalist's, the same grammar (see "A world's essences" above) |

**Where the tags live.** On a stat block the app already reads them live into the creature's
standing tags, beside `role.guard` (`rules/sheet.py`, the block's `tags`). The export has no
creature section, and "What is not here" keeps it so: no stat blocks. A world's own beast
therefore comes in, the day World Bible exports one, as **words and ids only**: the
bestiary template it fights as (an id) and its own `tags`. The proposed shape, for the
owner's and World Bible's review, is one row wherever a world names a beast:

```json
{"id": "5bbd0c40345f~creature:marsh-elk", "name": "marsh elk", "like": "elk",
 "tags": ["harvest.hide.5bbd0c40345f~material:marsh-elk-hide", "harvest.plan.quadruped"]}
```

`like` names the bestiary block whose numbers it has; the reader takes `type`, `subtype`,
`size`, CR, `resist`, `immune`, `reductions` and the natural armour in `ac_note` from that
block, so the export never carries a rules number. A beast with no tag falls back to the
generic rule.

**The generic rule** (plan §5.3, the reader's fallback, so an old world's beast still
yields; lane C's, not built yet: today's carcass excursions read only the tags that name a
material, `gathering.harvest_tagged`, and a creature with none by its name as before): animals and magical beasts give a generic fur hide unless their subtype or tags say
otherwise, vermin chitin, dragons scale; monstrous humanoids, aberrations, fey, outsiders,
plants, oozes, undead and constructs give nothing unless tagged. A generic hide is made the
beast's own from its stat block, never stored as a number: CR sets its tier (0 to 2 common,
3 to 5 uncommon, 6 to 9 rare, 10 to 14 exotic, 15 and up legendary), size its units, its
highest energy resistance or immunity one house resistance (÷ 5, at least 1), natural armour
+5 or more the `thick` trait, and on a rare-or-better hide its highest DR as DR
max(1, N ÷ 5) (owner, 2026-10-08, open point 6).

**What the stat block decides besides the hide** (lane C's reader; not built yet, the
shapes are the plan's and the owner's answers of 2026-10-08):
- **A dangerous body forces a second check while skinning** (open point 10): a poison
  special attack or poisonous flesh, an acid or energy subtype, a breath weapon, a body that
  burns or shocks to the touch, read from the block's tags and fields, never a list of
  names. A failure deals that creature's hazard: poison through the one poison door, acid or
  energy as damage of its type.
- **Harvesting a good outsider is a deed** (`type.outsider` with `subtype.good`), and so is
  a good-aligned dragon's, by kind (open point 12). A world whose own dragons are good says
  so with the bestiary's word in its tags, `subtype.good`; nothing reads an alignment line.
  Deeds are small signed values on the sheet and affect nothing yet (open point 11).

**Refused, with the fix named** (the app's validator on every load, and World Bible's on
export): a `harvest.hide*` tag on a humanoid ("humanoids are never skinned: remove the
tag"; the world owns its own races, but a person is never a hide), a tag naming a material
that does not exist, and a true dragon tagged with another colour's dragonhide (measured
before the revamp: a red dragon offered all eleven colours, inventory §0.4).

### Tanneries and leatherworkers

| Field | Meaning |
|---|---|
| `play.places[].kind: "tannery"` | read since 2026-10-06 (the places row's `kind`, above): a world's own tannery by any name ("the Tanyard", "Hide Row") is one, its keeper a tanner by occupation (`content/people/occupations.json` `tanner`, tag `leather`), with the vats, the lime pit and the hardening kettle for rare-and-up hides, rented by the hour and the vat by the day. Beside the smithy and the laboratory. Write it only for what the place IS. The kind word itself must be `tannery`: the app does not yet fold "tanyard" or "tan pits" to it (`places.KIND_WORDS`), so say `"kind": "tannery"` whatever the room is called |
| a settlement's own words | a tannery is appended on a settlement's **outskirts**, downwind of the last houses, when its own facts or paragraphs name its tanners: `tanner(s)`, `tannery`, `tanneries`, `tanning`, `tanyard(s)`, `tan pits`, `currier(s)`, `leatherworker(s)`, `leatherworking`, `the leather trade`, `its leather trade`, `leather goods`, `leather-workers`, `the hide trade` (`places.TANNERY_CUES`). "Leather" alone is not a cue (it describes what people wear: "iron-studded leather armor"), nor are "hides" and "pelts" alone (otter-herders selling pelts is trapping). No scale guarantees one: a tannery is rarer than a smithy. An authored town gets none appended: an author who listed the rooms has said what the town has |
| the leatherworker's counter | nothing from a world. **Every settlement**, village up, has a leatherworker keeper (`stall-lines.json`, the `leatherworker` shop, smallest `village`) selling the craft's supplies: curing salt, tannins, oils, waxes, threads, dyes, fittings, common hides and the field kit, always, at the catalogue's own prices (owner, 2026-10-08: "every town has a leatherworker and that person does not necessarily have a tannery") |
| `play.cast[]` tanners | words only: a person described as a tanner, currier, saddler, cobbler or leatherworker is the occupation `tanner`. A world's own word for the trade needs a row in that table |
| prices | none from a world: the yard by the hour and a vat by the day are the app's house rates (`market.tannery_rate`, `market.vat_rate`); hides and consumables at their own `price_gp` |

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

- **1.4** — two guarantees rather than two new fields, which is why it is a version and
  not a footnote. A 1.4 export promises that **`scale` is one of the words the consumer
  publishes** — its own three, or one of the aliases in `place-vocabulary.json`
  (`metropolis`, `hamlet`, `outpost`, …) — and that **a city carries `within`**, the
  room-to-room relation that makes a large settlement a square and four crossings rather
  than eighteen exits in one prompt. Both are additive on the wire: a reader that ignores
  `within` sees a flat list with correct exits and parents, which is what 1.3 was.

  Ruled 2026-09-16, when the supplier asked whether it was worth a number. It is: a
  consumer cannot tell by inspection whether a `scale` it does not recognise is a word
  the supplier forgot to translate or a world that genuinely has no such settlement, and
  a version answers that where a field cannot.
- **1.5** — three fields, each of which moves a decision from the consumer to the world.

  A race card carries `grants[]`, the tags themselves, and they are read INSTEAD of the
  prose rather than alongside it. A travel route carries `by` — `road`, `sea` or `river`
  — which settles how you get there rather than leaving a consumer to infer it from the
  continent tree. A settlement carries its own `places[]`, so a world that has written
  its rooms is not given generated ones.

  **In the JSON only.** Checked on the shipped 1.5 pair: the `races` table has no
  `grants` column and `trade_routes` has no `by`, so a consumer reading the SQLite mirror
  gets a 1.4 world that calls itself 1.5 — and gets it silently, which is the one thing a
  version number is supposed to prevent. Ask 10 in `docs/for-world-bible.md`. This app
  reads the JSON, so nothing here is broken by it; the next consumer will not be so
  lucky.

  Additive on the wire, and a reversal of authority for anyone who sends them: a 1.4
  export with none of the three is still read exactly as before, by the same guesswork
  as before. That is the whole point of the number — the guesses were often right, and
  a consumer cannot tell a right guess from a wrong one.
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
