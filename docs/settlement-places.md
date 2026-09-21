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

- **village** — the way in, the well
- **town** — the gate, the guardhouse, the well, the guildhall
- **city** — the gate, the guardhouse, the barracks, the well, the guildhall

A village has no guardhouse on purpose: a hamlet of four hundred has a reeve and a horn,
not a garrison, and inventing one would make every village a fort.

**A village has a way in, since 2026-09-21.** Asked for at the table — "every city/town
needs an entrance or two that is watched a village still has entry roads that are likely
watched as well" — and measured before it was built: eight of Aurvantis's sixteen villages
named no entrance of any kind, and a generated village's guaranteed set was a single well.
A settlement nobody can be seen arriving at is also one the law cannot watch, because the
warrant check in `_op_travel` asks whether the party is leaving by the way out.

It is a road and not a gate, which is the history as well as the fiction: walls and
ditches, "or sometimes just isolated gates, regulated trade and made collection of taxes
easier", so an unwalled settlement's entrance is about who is arriving and what they are
carrying rather than about defence.

A village went from five places to six at the same time, and for a stated reason: the
entrance is an addition rather than a replacement, and at five it crowded out one of the
four categories a player always reaches for.

## The vocabulary


### civic

| place | from | what reads it | what it is |
|---|---|---|---|
| the gate | town | travel | the way in and out |
| the way in | village | travel | where the road reaches the first house, and whoever is watching it |
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

## The ledger: 34 of 43 have no rule behind them

8 are read by something today — the market and the merchants row by the trade
rules, the smithy and the workshops by crafting, the gate and the way in by travel, the guardhouse, the
gaol and the barracks by the wanted state. The other 34 are rooms with names,
shapes and floor plans, which a scene can happen in and no rule consults.

That is not a defect by itself. A theatre the narrator can set a scene in is worth having
before anything mechanical reads it, and the shapes are real — an arena is banked seating
round sand, a lane is two walls and what is left between them, so a fight in one is not a
fight in the other. It is a promise, and this is where it is written down.

## Somebody is in them now

> "any place that offers services or merchandise needs an NPC to man it"

25 of these places sell something or do something for money, and `rules/places.STAFFED`
names three things for each: who ought to be there, the one person the engine stands
behind the counter, and the words the NPC codex is asked for. **`rules/keepers.py` builds
them**, since 2026-09-16.

A keeper is an ordinary actor in `Scene.people`, standing at their own place — so the
narrator's WHO IS HERE names them when the party walks in, and stops when they walk out,
with no code in either direction. Four things make them a person rather than a sentence
the narrator improvised:

- **named out of the world.** The settlement's own families first (Aurvantis writes four
  cast members per settlement, two families between them), the world's own given names
  behind that, and never a name the world already gave somebody. A world that ships no
  cast gets a keeper called what they are — "the smith" — because an invented name is a
  person the world does not contain.
- **the same person next time.** The pick is seeded off the place id, the same SHA-256
  that seeds the floor plan, so nothing is stored that could drift from the rule that
  made it.
- **numbers from the codex.** `rules/npcs.py` chooses a stat block by those role words
  near the party's level and writes it to `homebrew/npcs/`, so a keeper met at 1st level
  has the same numbers at 9th and one file on the NPCs bench corrects them. Measured:
  23 of the 25 find a real block; the workshops and the warehouses fall to the
  hand-written `guildhand`, which is what a guild hand is.
- **mortal.** The scene remembers which counters have been staffed, not who is standing
  at one — so the smith the party killed this morning is not behind the counter this
  afternoon.

- **kin, when there is kin.** Keepers are drawn from the settlement's own families, so a
  town of ten shops often has two Sootspars in it — and for a while nothing said so, which
  left the narrator writing two strangers who happened to share a name. Repetition, and
  repetition is what lazy generation looks like. Now a keeper who shares a surname with
  another keeper in the same settlement says whose household they both belong to. The
  engine states the relation and stops: whether they are close or feuding is the
  narrator's to play and the attitude track's to record. Ruled 2026-09-16 — *"they should
  be acknowledged by each other as family run stores"* — which also settled that one
  household running several shops is more real than three unrelated ones, not a collision
  to be bred out.

What was deliberately NOT built: a keeper owns nothing, stocks nothing and prices
nothing. Ultima Online gave its shopkeepers inventory, cash on hand and a supply-and-
demand simulation, the shopkeepers went broke holding goods nobody wanted, and the
simulation was abandoned rather than tuned. The shelf is `rules/market.py`, drawn and
not stored; the price is `rules/pricing.py`, out of the rulebook. The keeper is a person
to talk to.

`tests/test_keepers.py` holds all of it.
