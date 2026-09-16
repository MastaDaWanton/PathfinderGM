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
cue that was the only way to spot a port never fires.

## Still open

- **Nothing puts the party aboard on a sea journey yet.** A crossing passes the time; it
  does not stand them on a deck for it. So the engagement above is reachable by a scheme,
  by the narrator, or by a test — and not yet by simply taking passage.
- **Siege engines.** `arms` is on every row of the table and nothing reads it. A ballista
  on a warship's deck is a weapon the engine has no notion of.
- **The wind.** `days_for(with_the_wind=True)` halves a passage and nothing ever passes
  `True`, because the app has no weather.
- **Ships the party owns.** A vessel is bought, crewed, provisioned and repaired by
  nothing; `crewed()` answers the question and nothing asks it outside a boarding.
- **A ship as a place to live between passages.** The deck exists while an engagement
  does. Sleeping aboard, keeping cargo in the hold, and coming back to the same ship in
  port are all unbuilt.
