# What a settlement is made of, and what still has no rule behind it

Written 2026-09-15, when the place vocabulary was rebuilt.

> "there is no town or city that has 2 places. 2 places is a rest stop... cities and towns
> have businesses and entertainment and leisure/recreation and religious establishments/
> cultural buildings...the list goes on and on"

The table before that was six rows — a market, a gate, a tavern, a temple, the back
streets and the workshops — handed to a hamlet and a capital alike, and it never read the
`scale` the export has written on every settlement since 1.0. Aurvantis ships 16 villages,
32 towns and 16 cities; all 64 got the same six.

**This file is the ledger.** Most of these places are somewhere to stand and be described
and nothing more, and saying so is the same bargain `not_yet` makes on a race document:
the gap is written down rather than quietly implied. `tests/test_settlement_places.py`
holds this file to `rules/places.py`, so a row that gains a rule cannot leave a stale
entry here.

## How many, and how big

| scale | rooms | and | population, in the words the brief uses |
|---|---|---|---|

| village | 5 | flat — everything adjacent to everything | a few hundred people, and everyone knows everyone |
| town | 9 | flat — everything adjacent to everything | some thousands of people |
| city | 18 | a square and four crossings, so no prompt is wider than six | tens of thousands of people, most of whom will never see you |

A village and a town are flat because a settlement you can walk across is what a settlement
is. A city cannot be: eighteen rooms in one list is seventeen exits in one prompt, which is
what Fate's two-to-four zones and Inform's "small number of named positions" are about. So
a city is quartered, and `within` carries the shape.

## What every settlement of a scale always has

Not a category — a name. "civic" does not guarantee anybody keeping order, and a town with
nowhere to be arrested to is a town the wanted state cannot reach.

- **village** — the well
- **town** — the gate, the guardhouse, the well
- **city** — the gate, the guardhouse, the barracks, the well

A village has no guardhouse on purpose: a hamlet of four hundred has a reeve and a horn,
not a garrison, and inventing one would make every village a fort.

## The vocabulary


### civic

| place | from | what reads it | what it is |
|---|---|---|---|
| the gate | town | travel | the way in and out |
| the guardhouse | town | wanted | where the watch is, and there are always more of them inside |
| the guildhall | town | **nothing yet** | where the trades meet |
| the library | town | **nothing yet** | where the records are kept |
| the keep | town | **nothing yet** | where the soldiers are, and the walls they hold |
| the moot hall | town | **nothing yet** | where the arguments are had in public |
| the gaol | town | wanted | a room with a lock on the outside |
| the barracks | city | wanted | where the watch sleeps and drills |
| the courthouse | city | **nothing yet** | where it is decided, and written down |
| the customs house | city | **nothing yet** | what came in, and what was paid on it |

### faith

| place | from | what reads it | what it is |
|---|---|---|---|
| the shrine | village | **nothing yet** | somewhere to be quiet |
| the graveyard | village | **nothing yet** | the ones this place has already lost |
| the temple | town | **nothing yet** | somewhere to be quiet, with a roof on it |
| the cathedral | city | **nothing yet** | too large for the town under it |

### hidden

| place | from | what reads it | what it is |
|---|---|---|---|
| the lane | village | **nothing yet** | round the back, and out of the light |
| the back streets | town | **nothing yet** | where nobody is watching |
| the warrens | city | **nothing yet** | a street plan nobody drew |

### leisure

| place | from | what reads it | what it is |
|---|---|---|---|
| the inn | village | **nothing yet** | a bed, if you can pay for it |
| the green | village | **nothing yet** | the common ground, and what happens on it |
| the tavern | town | **nothing yet** | somewhere to sit down |
| the bathhouse | city | **nothing yet** | steam, and everybody business in it |
| the theatre | city | **nothing yet** | where the town watches itself |
| the arena | city | **nothing yet** | sand, and a crowd that paid to be there |
| the gardens | city | **nothing yet** | kept, and walled, and not for everybody |

### trade

| place | from | what reads it | what it is |
|---|---|---|---|
| the market | village | market | where the stalls are |
| the smithy | village | crafting | a hearth, an anvil, and the noise of both |
| the mill | village | **nothing yet** | the wheel, and the sacks stacked against it |
| the workshops | town | crafting | where the trades are |
| the tannery | town | **nothing yet** | the smell reaches the next street |
| the brewery | town | **nothing yet** | vats, and the heat coming off them |
| the warehouses | town | **nothing yet** | what the town is holding, and who for |
| the mine head | village | **nothing yet** | where the ore comes up |
| the counting house | city | **nothing yet** | ledgers, and somebody who knows what you owe |
| the merchants row | city | market | the expensive street |

### transport

| place | from | what reads it | what it is |
|---|---|---|---|
| the stables | village | **nothing yet** | horses, and the people who know them |
| the docks | town | **nothing yet** | where the boats come in |
| the bridge | town | **nothing yet** | over the water |
| the carters yard | city | **nothing yet** | what leaves at dawn, and on whose account |

### utility

| place | from | what reads it | what it is |
|---|---|---|---|
| the well | village | **nothing yet** | where the water is |
| the granary | town | **nothing yet** | what stands between this winter and the next |
| the midden | town | **nothing yet** | where it all ends up |
| the cistern | city | **nothing yet** | under the street, and older than it |

## The ledger: 34 of 42 have no rule behind them

8 are read by something today — the market and the merchants row by the trade
rules, the smithy and the workshops by crafting, the gate by travel, the guardhouse, the
gaol and the barracks by the wanted state. The other 34 are rooms with names,
shapes and floor plans, which a scene can happen in and no rule consults.

That is not a defect by itself. A theatre the narrator can set a scene in is worth having
before anything mechanical reads it, and the shapes are real — an arena is banked seating
round sand, a lane is two walls and what is left between them, so a fight in one is not a
fight in the other. It is a promise, and this is where it is written down.

## The one that is a real gap: nobody is in them

> "any place that offers services or merchandise needs an NPC to man it"

25 of these places sell something or do something for money, and
`rules/places.STAFFED` says who ought to be standing in each. **Nothing generates them.**

That is the next piece of work on this and it is a real one, not a table entry: a keeper
needs a name the world would actually use, a place in the NPC codex, and to still be there
next session — which is the difference between a shopkeeper and a sentence the narrator
improvised and forgot. Until then the narrator may describe whoever is behind the counter,
and the engine does not know them.

