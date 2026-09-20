# The map, and who a place holds

Group 11 of the fix pass after the 2026-09-19 play-test
(`docs/playtest-2026-09-18.md` item 28). Branch `map-and-roster`. Tests:
`tests/test_map_and_roster.py`.

**Reported.** *"A map should be displayed at all times and Enemy/NPC spawns should not be
random but based on the situation and narration should match it."*

## The map

**What was wrong.** The grid existed only inside a fight, by construction: laid by
`_lay_battlefield` from the two doors a fight comes in by, cleared by `end_encounter`,
gated again server-side and in the browser, which printed *"No ground is mapped. A grid is
laid out when a fight starts."*

**Nothing was missing to derive one.** `floorplan.for_place(place_id, terrain, authored)`
is a pure function, its scatter is a SHA-seeded LCG rather than `random`, and all three
inputs are available on every turn — so the market has the same stalls every time anybody
stands in it and none of it is saved. What was absent was **positions**, and the zone word
(`engaged`/`near`/`far`) is on every actor at all times, which is exactly what
`place_by_zone` reads.

**Prior art.** This is what every virtual tabletop does: the map is the room, and the
tactical layer is a toggle on top of it — Foundry ships a
[Tactical Map](https://foundryvtt.com/packages/tactical-map) module precisely so a
theatre-of-the-mind game can "solve combats more tactically" on ground that was already
there.

**Built.** `Engine.lay_the_ground()`, called when the party arrives somewhere
(`place_party`). `end_encounter` no longer clears the grid; the ground belongs to the
place, and what ends with the fight is initiative, sides, and the things a fight conjured.
The grid is replaced where it is replaced: arriving somewhere else.

### Three regressions the suite caught, which are the interesting part

Making the map permanent broke fourteen tests. Three were real:

1. **A reload re-derived the grid**, because loading a campaign runs `place_party` — and a
   fog cloud that had survived the restart lost its squares to the fresh ground
   (`test_a_fog_cloud_survives_closing_the_app`). The ground is now replaced only when the
   place actually *changes*.
2. **A fight in a scene with no place got no ground at all.** A scene with nowhere in it is
   one that has not been put anywhere yet — the map tray says so rather than drawing a
   blank field — but a brawl still happens on ground. `lay_the_ground(even_nowhere=True)`
   is the fight's door.
3. **The fight stopped laying out its own combatants**, because the layout skips anybody
   who already has a square — so a stated "I loose an arrow at him from 200 feet" opened at
   forty. A fight now clears and re-lays its combatants' positions.

The third is a real trade, taken deliberately: a zone word and a stated distance are claims
about the **fight**, and an idle position from standing about in the room is not. Bystanders
keep where they were standing; the fight lays out the fight. The nicety of "the man at the
counter is still at the counter when the brawl starts" is lost for combatants and kept for
everybody else.

## Who this place would hold

**What was wrong.** There is **no randomness in the spawn path at all** — no `random`
import anywhere in it, and `_free_spot_at` and `npcs.choose` are both explicitly
deterministic. The complaint was about *appropriateness*, and it was well founded: who
appeared was decided by three regexes over the player's own sentence falling through to a
literal `"thug"`, and the model was offered exactly **four** templates while 7,133 stat
blocks sat loaded and reachable.

The situational material was written and unread: `places.STAFFED` (25 rows of who is at
each kind of place, and the words to search the bestiary with — its only caller in the repo
was a tooling script), `places.category_of`, `npcs.choose` with a CR band, and the world's
own residents.

**Prior art.** Left 4 Dead's Director is the reference design: it places enemies "based upon
each player's current situation, status, skill, and location" with [structured
unpredictability](https://steamcommunity.com/sharedfiles/filedetails/?id=147309463), over a
set of **threat locations the map author placed**. This app already had both halves — the
places are the authored locations, the cards and the settlement's tension are the intensity
— and lacked only the roster.

**Built.** `rules/roster.py`: `who_would_be_here(scene, world, level)` reads, in order of
how specific each source is about *this* place — the place's own `STAFFED` row, the live
cards' people, two of the settlement's residents, then the category and then people going
about the day. Every entry is resolved against the corpus inside the CR band, so nothing in
the list is a creature the party cannot meaningfully meet. The brief prints it as fact, and
`_SPAWN_HINT` stops listing four templates as though they were the world.

### What the measurement changed

Residents were going to contribute their **role words**, as the plan said. Measured against
the shipped export, a Pangrella resident's `Role` fact is prose — *"Innovative developer and
expert in magnetic shift adaptation"*, *"High King's Representative"* — and handing that to
`npcs.choose` returned a Drummond-and-Neville and an Initiate of Flame standing in the
market. (Aurvantis writes clean roles: guildmaster, law-speaker, harbor-reeve. Neither
export can be relied on, so neither is.) Residents contribute their **name**, with a stat
block from the codex path world characters already use, and only two of them: a roster
swamped by names is one the model cannot choose from.

Item 29's rule is untouched. The roster is a list of who could plausibly be here, not a
claim that they are — the engine still has to be told to create anybody, and whose word
somebody exists on is still the test.
