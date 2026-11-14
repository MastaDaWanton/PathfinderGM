# Ships, the sea between continents, and boarding

`rules/ships.py`, `rules/journey.py`, `Engine._op_sea`, `tests/test_ships.py`. Written
2026-09-16, from two rulings given the same day.

## The rulings

> **Ships close, and then people board. The fight is on the deck.**

> **Continents are separated by water unless otherwise specified**, and there is both land
> and sea travel unless every place is on the coast.

## Why not the full naval system

Pathfinder offers two. Ultimate Combat's vehicle rules give ships vehicular bull rush,
overrun, ramming maneuvers, crew stations, and siege engines with reload times — a
simulation this app's narrator would have to describe every round. The GameMastery Guide's
fast-play rules are eight lines and a mat at thirty feet to the square.

Neither is quite right for a game with no picture, and the reason is documented in public.
**Pillars of Eternity II shipped text-based ship-to-ship combat** and reviewers called it
the worst naval combat in any RPG they had played. The specific failures are the ones a
narrated text game walks straight into:

- the player could not tell how the two ships were oriented, because there was nothing to
  look at;
- the exchange was tactically trivial;
- the winning move was always to close and board, which made the whole system a tedious
  prelude to the fight that actually mattered.

So the distance between two ships is a **band**, not a grid, and the interesting decisions
are what you do while it shrinks. Three words a player can hold in their head from prose
alone:

| band | what it is |
|---|---|
| `distant` | a sail on the horizon. Run, or turn and close |
| `closing` | bowshot. Arrows, spells, and the last round in which running is cheap |
| `alongside` | oars touching. Grapnels, planks, and the fight is a deck away |

## A ship is a place you stand on

Not a creature, not a vehicle object. Everything follows from that:

- **the deck is a place with a floor plan**, so a fight on it is a fight this engine
  already runs — the mast to put between you and them, a rail with the sea past it,
  below-decks through a hatch;
- **going over the side is a move into the `water` place**, which `rules/water.py` already
  owns: the underwater table, the drowning clock, all of it;
- **the vessel is a small record** the scene holds, because unlike a room it MOVES, and how
  much of it is left is a fact play made rather than one anything can recompute. That is
  why vessels are stored where places are derived.

`deck` is its own terrain for a mechanical reason rather than a tidy one: a creature
standing on planking is not swimming, so none of the underwater table may reach them.

Ship ids are `ship-` and twelve hex characters, shaped like a World Bible entity id. The
first version read `ship:<port>:<kind>:<n>` and broke this app's own id grammar — the
parent half of `{parent}~{terrain}:{slug}` may not contain a colon — so `terrain_of` came
back with the empty string, which is the published way of saying "this place stands on
nothing". A blank field to fight on, which is exactly what the grammar exists to prevent.

Since 2026-11-13 the kind rides in the id too (`ship-sailing-ship-<hex>`), so a ship's rooms
derive from a place id alone. An id from before (`ship-<hex>`) would get none; no save holds
one, because nothing outside a test wrote `scene.vessels` or a non-empty `scene.sea` before
that commit (f01af11c). `tests/test_sea_encounters.py` pins that every door minting an id
since carries its kind.

## Table 7-49, transcribed

Keelboat, longship, sailing ship, warship, galley: AC, hit points, base save, speed, arms,
ram damage, squares, crew. Hardness 5, wood. Nothing tuned.

**A rowboat is deliberately absent.** It is not on that table — it lives in the vehicle
rules, which this does not use — and adding a row would be inventing Pathfinder.

Sinking is the book's: 0 hit points is the *sinking* condition and not the bottom. Ten
rounds, one less for every 25 damage after, which is the only reason a ship fight has a
clock worth feeling. Everybody aboard has that long to be somewhere else.

A ship below her crew minimum does not move. That is the quiet reason you cannot simply
steal a warship.

## The five verbs

`{"op": "sea", "params": {"do": "..."}}`

- **close** / **sheer off** — one band a round. Sheering off at `distant` ends the
  engagement, which is a real outcome and the one a merchantman wants: these ships are
  faster than they are tough, and a fight you can decline is a fight worth having.
- **ram** — from `closing` only, because the book wants way on and a run at them
  ("must move at least 30 feet and end with its bow adjacent"). A **Profession (sailor)**
  check at the helm against the target's AC. Profession is trained-only and that rule has
  teeth here: a party with nobody who has sailed cannot ram anybody, and the refusal says
  what is missing rather than quietly rolling a check the book does not allow. A hit deals
  the table's ram damage to them and **the minimum of your own ram dice to you**.
- **grapple** — at `alongside`. The one thing in the engagement that cannot be taken back
  in a round, which is what makes throwing them a decision rather than a formality.
- **board** — across to their deck, with anybody named in `with`. And **somebody is
  waiting**: the watch at the rail comes from the NPC codex by role words at the party's
  own level, the same door a shop's keeper and a scheme's cast come through. A handful and
  never the crew list — a galley carries two hundred rowers, and two hundred creatures is
  not an encounter. What the count says is how many were quick enough to be there; the rest
  are why the fight has to be won before they come up.

## Where the water is

Derived from the tree the export already carries: two settlements whose ancestors run up
through different `CONTINENT` entities are across water from each other. **A stated `road`
is the "otherwise specified"** — a world that wrote one between two landmasses has said
there is an isthmus or a causeway, and a thing the world said beats a thing this app
worked out.

Measured the day the rule was made: **48 of Aurvantis's 48 travel legs cross a continent
boundary**, and 2 of Pangrella's 5. Every one was being walked. That is not a defect in the
export — a trade route is an economic relationship, and "Brackgate sells tempered steel to
Ashwatch" was never a claim that you can walk there.

A crossing runs at the ship's speed for **24 hours a day**, because a ship keeps watches
and does not camp at dusk; that is most of why the sea is faster than the road at the same
speed. Nobody aboard is marching, so the journey op moves the clock without charging the
body — which is what `_march`'s camp does for a traveller anyway, minus the walking.

**Not every place is on the coast.** A settlement is a port when it has somewhere to tie
up, and a crossing that starts inland starts on a road: *"the road to the coast, and then
four days at sea"*. The numbers behind that are an ask rather than a bug — see ask 8 in
`docs/for-world-bible.md`. Aurvantis has 11 ports of 64, every one of them minted by this
app's own cue table out of the settlement's prose; **Pangrella has none of 12**, because
its places are authored, an authored list replaces the generated one by design, and so the
cue that was the only way to spot a port never fires. (Stale by 2026-11-13: the fixture's
places are generated again, and Pangrella has 4 ports of 12, two on each continent.)

## Taking passage (2026-11-13)

> Owner: "make ships boardable and have sea/ocean travel be accessible" — "I should be able
> to get on a boat and travel" (ruling 2026-11-09) — and "over sea/ocean travel should be
> rolled by the day with a small chance based on volatility to have storm wreck the ship".

**The doors are the journey op's**, so every way a land journey is chosen reaches a ship:
the exits row (from the docks a sea leg is a `road` row, and `views._take_the_exit` sends
`journey to=<id>`), the reader (`journey` act, "book passage", "set sail"; or a `go` naming
a town the legs reach, `interpret._road_to`), and the planner (the brief's ABOARD line,
`gm/brief/roads_out.py`, names where she is bound).

1. **Book** (`Engine._book_passage`): at a port, a sea leg that is not a river buys a berth
   on the port's sailing ship (`ships.passenger_ship`) for **1 sp a mile a head** (CRB
   Table 6-9; Adventurer's Armory's Transport, Sea table agrees) out of the purse, the
   miles the world's when stated, else the ship's day's run times the days. The party and
   anybody travelling with them stand on her deck — a real place, `places.for_scene`
   derives a ship's rooms from the place id (the kind rides in `ship-<kind>-<hex>`), the
   deck and the docks a gangplank apart while she lies at the quay. The master and a hand
   are aboard, from the NPC codex. A berth booked and not sailed is re-boarded free.
   **The fare moves with the seller** (owner, 2026-11-13: "keep the rulebook's base price
   augmented by the relationship and the personality of the seller"). The seller is the
   port's harbourmaster (`Engine.passage_seller`, the docks' keeper), who is on the docks
   when the fare is quoted; the ship's master is only minted on deck after a berth is
   bought. `Engine.passage_terms` takes the book's fare through the shop's machinery: the
   law's markup (`pricing.markup_for`), then percent off by `tradecraft.buy_price` — the
   seller's attitude (`pricing.REGARD_PERCENT`: hostile +25%, unfriendly +10%, friendly
   -5%, helpful -10%, devoted -15%), their thrift (a point per 5 off the middle, silent
   within 10; a keeper with no life recorded has a score seeded by their world id,
   `lives.axis_score`) and the day's haggle with them (`_op_haggle`, kept under their stall
   key), never more than 25% off. The quote in the exits row and the coin taken are one
   number (`passage_quote`), and the tell names the reason when it moved ("The
   harbourmaster likes you: 5% off the book's fare."). Every keeper's counter reads the
   same terms since the owner's ruling of the same day (`tradecraft.counter_terms`).

   **Talking with the harbourmaster offers the berths** (`views._passage_offer`,
   `scene.passage_offer`): measured live, "I ask the master for passage to Mirabalos, pay
   the fare and go aboard" was read as talk and booked nothing. While the engine holds the
   player in conversation with the harbourmaster, the exits row's own passage rows are
   offered above it as "Book passage to X"; a click attaches the same journey chip and Say
   books it. Nothing reads the words for it, and the brief tells the narrator the fares and
   that nothing is paid in the prose. A "-master" title answers to "the master"
   (`keepers.trade_words`).
2. **Sail** (`Engine._sail`): aboard a booked ship any journey is the voyage. She casts
   off (the location becomes the ship: no town's rooms are a walk from her deck at sea)
   and makes way a day at a time — the clock's day, the ship feeding, watering and
   bedding her passengers as a camp's night does — until port, a storm, or `days`. A rest
   aboard at sea is time she sails; the next sail does not charge it twice.
3. **The weather**, once a day, hidden (`ships.day_at_sea`): a storm on 5% of days —
   Ultimate Wilderness Table 4-28's windstorm band (96-100) — times the waters'
   `volatility.factor` (the worse of the two ports'; calm 2.5%, lawless 10%), and one storm
   in ten is the wrecking kind (CRB Table 13-9: 91-99 storm, 100 powerful storm). So 0.5%
   a day at the published rate; a seven-day crossing is wrecked about one time in thirty.
   A storm she rides out is an effect on everyone aboard (the CRB storm's -8 Perception,
   for the day) and a tell, and stops the day's sailing. The effect carries the tag
   `weather.no-ranged-weapons`, and the attack op refuses a ranged or thrown weapon under
   it with the reason said: "Storms make ranged weapon attacks impossible, except for those
   using siege weapons" (CRB p.438; nothing here fires a siege weapon). Spells are not
   weapon attacks and the CRB does not stop them.
3b. **The sea itself**, once a day after the weather, hidden (`ontheway.sea`, 2026-11-13):
   one check at the road's published 20% (Ultimate Wilderness p.127; one a day, as
   Pathfinder 2e's Gamemastery Guide rolls travel), and on a hit, d100: merchant 1-35,
   naval patrol 36-50, pirates 51-70, a creature 71-100. Half the hits pass, the shape of
   PF2e's harmless/hazard/creature split; the pirates and the creature widen with the
   waters' `volatility.factor` (as the storm's chance does) and the passing sails never.
   So 10% a day of something dangerous at the published rate, ~4% pirates and ~6% a
   creature. Not on a river, and not on the day she makes port. Every hit stops the day.
   - a **merchantman** or a **patrol** is told and passes;
   - **pirates** are a vessel minted for the meeting (a longship or a sailing ship) and
     the bands below at `distant`. **Sheering off is a leg of a chase** (`Engine._run_from`):
     the faster hull (Table 7-49's speed) gains a band; at equal speed the two helms make
     opposed checks — Profession (sailor), Ultimate Combat's driving check for a sailing
     ship, or Wisdom for anybody untrained ("a driver can always make a Wisdom check in
     place of a driving check") — ties to the higher modifier (CRB opposed checks), then
     rolled again. The winner of a leg moves the band its way; a runner who wins at
     `distant` is away. No 1e book races two ships: Ultimate Combat's vehicles say nothing
     of pursuit, and the GameMastery Guide's chase (whose example is two sailing ships
     racing for an island) gives +2 a check per 10 ft over the baseline instead — not used.
     Closing, or losing the chase to alongside, and she comes
     **alongside and boards the party's deck** (`Engine._pirates_come_aboard`): the rail's
     count from the codex's pirates, trimmed on the **wandering** mix — a sail met on the
     water is a wandering encounter wherever it is fought — and the fight opens on their
     turn. Boarding *them* instead meets their rail on the guarded mix and opens the fight
     too. Once every boarder is down or gone, the next sail cuts her loose and goes on
     (`Engine._sea_settled`), standing a party left on her deck back on their own;
   - a **creature** is drawn from the bestiary's `water` biome narrowed to salt water by its
     own Environment line (`ontheway.open_water`: an otter, a naiad and a kappa were all
     mid-ocean meetings before), at the party's budget (wandering, `encounter_budget`). One
     that comes at you (the road's aggressive types) starts the fight with the party's
     turn; one with a swim speed waits **in the water at the rail** beside the player
     (`Engine._into_the_water`), to strike from it or climb aboard, and one without comes
     over the rail. Any other surfaces, looks, and goes.
   - **The water on the board.** The rail's squares and the sea's are open water
     (`Grid.water`, a fixture kind with `swim`): solid to a walker, open to a creature with
     a swim speed, and to anybody who goes over the side, at four times the cost (CRB
     Swim: a quarter of their speed a move action). Whoever stands in it is in
     rules/water.py's table (`Scene.afloat`, `Actor.water_row(afloat)`) and, without a swim
     speed, makes the Swim check once a beat (`Engine.swim`: DC 10 calm, 20 stormy under
     the storm at sea; fail by 4 or less, no progress; by 5 or more, under and onto the
     breath clock). The rail still covers from outboard and the sea covers nobody.
   The Bestiary's own Ocean table (pp.324-327) is creatures only; no Pathfinder 1e sea
   rate or ship table could be read (Skull & Shackles, Stormwrack), and none is claimed.
4. **The wreck** (`Engine._wreck`): the ship and her crew are lost. Passengers swim for
   1d4 hours (the app's number) in stormy water — the Swim skill's DC 20 each hour or 1d6
   nonlethal (CRB, Swim) — come ashore fatigued (the hustle precedent: lifts after 8 hours
   of rest), lose their raw materials to the sea and each loose good on a coin toss (a
   stated house rule; no 1e book prints one), and wash up on the shore of the port the
   ship was nearer, or one time in four on another port's shore. Every number lands with
   `origin: rule:shipwreck` and the narrator is told the tell.
5. **Arrival**: the ship ties up at the far docks and the party goes ashore.

**Every crossing by water is this one path** (integrator's run, 2026-11-13: Vormoor to
Ledgerwarren was still the old free crossing while the way back was paid). From a town
with no docks the passage is booked where the player stands and **the road to the harbour
is walked first** (fix/overland-to-the-port, 2026-11-14; see "The road to the
harbour"). A river is a passage on a keelboat, and no storm is rolled on it. Whoever does not come aboard is left as the road leaves them. The exits
row prices the passage from the same quote the booking charges (`Engine.passage_quote`).

**Boarding crews are budgeted** (`Engine._defenders`): the rail's count (up to four, by
the hull's crew) is trimmed by `encounter_budget.most_of` on the **guarded** mix — a crew
on her own deck is defending it, the owner's "guards and lairs may be challenging or hard",
and the party chose to board.

Researched and not used: Skull & Shackles' own weather table (Tempest Rising p.72) and
Stormwrack's storm and shipwreck rules could not be read; nothing here claims them.

## The road to the harbour (2026-11-14)

0.3.2 booked a crossing from an inland town and stood the party on a deck with **0 minutes
on the clock**: Vormoor's road to Scrapden, its nearest port, is 96 miles, five days on
foot. Now `_op_journey` asks `journey.coast_road` first, and when a road comes before the
ship it walks that road as **the journey it is**: the CRB's overland pace (Table 7-8 by
speed, 7-9 by terrain and road, `journey.hours_for`), the road's watch checks
(`ontheway.road`, budgeted by `encounter_budget.party_apl` and `volatility.scale`), the
march's food, water and camps (`_march`), mounts, escorts, a road stopped short and
resumed. On arrival the berth is bought at the harbour's quay at its own price
(`passage_quote(port=)`), and the ship sails from there.

**Book inland, be walked there — decided, not "go to the port first".** Measured on
Aurvantis that day: 52 stated sea legs start inland, **36 of them end inland too**, and no
port's legs reach an inland town (passages are offered port to port), so making the player
walk to a port and book there would strand every one of them. 39 of the 52 have a road to
a port; the quickest one is the coast road. The other 13 (and all 3 of Pangrella's) have
no road to any port: those walk a derived day (`journey._depth_apart`'s smallest step,
told "how far, nobody has written down") and board off the town's own shore, as before.
The fare is checked before the road is walked, so nobody marches five days to be told at
the quay that the purse is short. The From Here row and the roads-out brief both say the
whole trip: "about five days on foot to Scrapden, then a day at sea, … passage", and a road
stopped short keeps the crossing (`scene.road["then"]`) so the row offers it from the
stretch of road. The row is offered where the harbour's road leaves (its head, as the road
itself is), not from the town's shore: Vormoor's shore is a quarter of an hour out and the
ship is five days away. Measured live (Aurvantis, Vormoor to Ledgerwarren, 500 gp): two
watch checks met a toll-keeper on days 2 and 4, each further journey resumed the rest of
the road, and the party boarded the Storm Compass at Scrapden on day 5, about 101 hours
after setting out, the fare taken at Scrapden's quay.

Prior art: Daggerfall's travel map quotes one total for a trip that includes the sea
(UESP, Daggerfall:Traveling); I could not confirm from a primary source whether it forbids
boarding outside port towns, and nothing here claims it.

## Still open

- **The derived coast.** An inland town with no road to any port walks a derived day to
  a coast the world never placed, and boards off its own shore; the export would need to
  say where the water is (for-world-bible 8a/8c).
- **The far end inland.** A crossing to an inland town still ties up at that town; the
  road up from its harbour is not walked yet.
- **Siege engines.** `arms` is on every row of the table and nothing reads it. A ballista
  on a warship's deck is a weapon the engine has no notion of.
- **The wind.** `days_for(with_the_wind=True)` halves a passage and nothing ever passes
  `True`, because the app has no weather.
- **Ships the party owns.** A vessel is bought, crewed, provisioned and repaired by
  nothing; `crewed()` answers the question and nothing asks it outside a boarding.
- **A ship as a place to live between passages.** The deck exists while an engagement
  does. Sleeping aboard, keeping cargo in the hold, and coming back to the same ship in
  port are all unbuilt.
