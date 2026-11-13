# The turn budget and named fixtures: plan

*2026-11-06; Part 2 phase 1 built 2026-11-11 (below). Owner rulings that day: multi-step plans are fine outside a fight, but "once a
limit of actions has been hit the world doesnt stand still it moves as well". The map
"needs a little upgrade". Not built yet.*

## The rulings this builds to

1. **The budget.**
   - Moving around the place you are in is free.
   - A turn holds up to two quick deeds (take, give, open, eat, look).
   - The turn ends at once when:
     - a deed **takes time** (cooking, crafting, searching a room, a long talk);
     - the player **addresses someone who would answer** (asking, offering, threatening, insulting), so they get to reply first;
     - **a roll fails**, which already stops the chain.
2. **When the budget is spent, the world moves.** The people present take their beat (the "Continue means the scene moves" ruling, 2026-09-18). Someone may ask a question. The turn ends with options, and the unrun steps stay in the input box.
   - The owner's own example: "I run to the other side of the room and begin cooking dinner then i serve the food i made to everyone". Run (free) → start cooking (takes time: turn ends) → the family does its own thing, one of them asks a question → options: answer the question / put the finishing touches on the meal / throw the hot food across the room and storm out. "Serve everyone" waits in the input box.
3. **Named fixtures on the map.**
   - The stair, the barrels, the wine rack and the bar get squares and properties. Each fixture gets its square when the scene first names it and keeps it from then on (the 2026-09-28 ruling that people keep their square, extended to things).

## What already exists (checked 2026-11-06)

| Need | Exists | Gap |
|---|---|---|
| Splitting a line into steps | `gm/sequence.py`: Inform/Infocom clause chains; a failed step stops the chain; unrun words go back to the input box (`views._unfinished`) | No budget: every clause runs this turn |
| Work that takes time | `rules/inprogress.py`: crafts as works counting down on the world clock | Only crafts. "Cooking dinner" is not a work yet |
| The world taking a beat | the Continue path (`prompts.CARRY_ON`), NPC beats | Not triggered mid-line when a budget runs out |
| Options at the end of a turn | `play/aftermath/suggestion_sheet.py` | Not told what was left unfinished or what was asked |
| The map | `rules/grid.py` and `rules/floorplan.py`: walls, pillars, rubble, raised floor, parapets, deterministic per place | The floorplan deliberately has **no named features** ("decoration belongs in the prose") |
| Things reached for | `gm/scenery.py`: a prop becomes real when the player reaches for it; Fate's "established and usable" | A prop has no **square**, and fixtures are found by a regex (`judgement._FIXTURES`) |

## Part 1: the budget

**Where:** the sequence runner in `gm/agent.py` / `play/views.py`, the code that walks `sequence` clauses through `_plan_and_run`.

1. **Each clause's cost comes from the reader, not from English.** The reader already reads the line into closed acts. Add one closed field per action, `cost`, with these values:
   - `free`: movement inside the place, speech with no one to answer;
   - `quick`: take, give, open, eat, look;
   - `takes_time`: cook, craft, search a room, rest, a long task;
   - `addresses`: asks, offers, threatens, insults someone present who can answer.

   Code validates the field against the turn's acts and the people present. For example, `addresses` must name a ref who is here. No regex decides the cost (the owner's direction of 2026-10-03).
2. **The runner keeps count.** Clauses run in order while `quick` ≤ 2. The turn stops after the first `takes_time` or `addresses` clause, or after a failed roll. The rest go to `unfinished`, exactly as a failed chain's do today, with the line "Not yet done: serve the food".
3. **Starting a time-taking deed starts a work.** `inprogress` is generalised beyond crafts with a plain `task` work kind ("cooking dinner, ready in about an hour"). It counts down on the world clock like any craft, so "put the finishing touches" next turn finishes a real thing. The duration comes from a small closed table of everyday tasks (cook a meal, mend a garment, search a room, write a letter); a task the table does not know gets a default band. A model never sets a duration.
4. **The world's beat.** When the budget ends the turn, the people present get the Continue beat, the same machinery as pressing Continue. They act for themselves, and one may put a question to the player. That beat is planned as an NPC turn, so the narrator only writes what the engine decided.
5. **Options.** The suggestion sheet is handed three things: the unfinished clauses ("serve the food"), the open question if one was asked ("answer Mira"), and the in-progress work ("put the finishing touches"). The player's own way out ("storm out") stays the player's to type; the sheet offers a few, it does not limit.

**Measured before and after:**
- a set of 30 multi-step lines (dinner, the lock-and-gold heist, ask/take/leave), with the deeds run per turn counted;
- the count of NPC beats;
- whether the unfinished words came back;
- the existing narration bench, which must not move.

## Part 2: named fixtures

1. **A closed list of fixture kinds and their properties** (a new `content/rules/fixtures.json`):

   | Kind | Properties |
   |---|---|
   | stair | climbable, raised, narrow |
   | door | blocks, opens |
   | window | opening, see-through |
   | table | cover, low obstacle, movable, flippable |
   | counter / bar | cover, low obstacle |
   | barrel | cover, heavy, rollable, flammable when oil |
   | rack / shelf | blocks, breakable |
   | hearth / fire | burns |
   | chandelier | overhead, swingable |
   | cart | raised, cover |
   | crane | lifts |
   | water | difficult, swim |

   Each property is something the engine already reads: cover, `parapet`, `blocked`, `difficult`, `floor`, burning.
2. **A fixture is placed when the scene first names it.** This is the scenery module's own rule ("ledgered from the narration that showed it"), extended with a square.
   - The reader names the fixture kind from the closed list. Code places it on a free square near the people the sentence placed it by ("behind the clubman"), or else by the place's deterministic seed, and it keeps that square for good.
   - The scene's own words seed it too: a World Bible place or a scene fact that names "a narrow stair" lays it at the start.
   - `judgement._FIXTURES` (a regex) is retired in favour of the reader's closed answer.
3. **The engine uses fixtures:**
   - cover and low obstacles in the attack modifiers it already computes;
   - raised ground for the +1;
   - "back to the stair", checked against the stair's square and where the foes stand;
   - a barrel rolled to block a stair becomes `blocked` or `difficult` squares (a Strength check);
   - a creative use of a named fixture gets its +2 from the judge **only if the fixture exists**.
4. **The map shows them**, drawn on the existing table grid with the same look.

### Phase 1, built 2026-11-11 (branch feat/map-fixtures)

The owner, that day: "we had talked about adding crates and barrels bookshelfs stairs etc..
lets do that now". Amended from the plan above where building it said otherwise:

- **It types the geometry that exists; it lays none.** Campaigns have people on today's
  derived maps, so a fixture is a name for squares the floorplan already made solid,
  rough or raised (`rules/fixtures.py`, kinds and per-place rows in
  `content/rules/fixtures.json`, validated on load). Derived from the pristine plan
  intersected with the grid, so a spell's wall is never typed and nothing is saved. The
  only addition is a stair at a gallery's foot, which is walkable and so can never put a
  saved position inside anything (`tests/test_map_fixtures.py`, every place of all three
  exports). Two kinds the plan lacked were needed: `gallery` (the ledge band a stair
  reaches) and `rubble`; the owner's `crate` and `bookshelf` are their own kinds.
- **The engine reads:** a low fixture (table, counter, barrel, crate, cart, hearth) is a
  parapet one level up for sight and cover — cover, never total (CRB p.195); a gallery
  with a stair is walked onto without a climb speed; a raised crate or cart names its
  Climb DC in the refusal. Found on the way: a move written (x, y) without its level
  walked anybody straight up a ten-foot gallery that (x, y, 2) refused — closed.
- **The reader** gained a closed `fixture` on its `go` act (enum from the file); a
  narratable kind the room lacks is put on a free square by the player and kept for good
  (`Scene.fixtures_named`). `judgement._FIXTURES` is NOT retired: its regex caller
  `judgement.movement_within` (dropping a travel/found the plan wrote for a walk across
  the room) reads the player's words, not the reader's frame, and `interpret.within_place`
  still falls back to its noun list when the reader says neither `within_place` nor
  `fixture`. Retiring it needs `keep_movement_in_the_scene` to be handed the frame.
- **World Bible** may author `fixtures` on a place (docs/for-world-bible.md ask 15).
- **A walk to a fixture moves the token** (the owner at the gate, same day: "the
  narration let him go up the stairs but the character never moved on the map"). A
  `go` with a `fixture` builds a real `move` (`fixtures.walk_to`): to a gallery's free
  square nearest its stair, a stair's square, the floor beside something solid, or —
  the reader's `floor` — back down to the stair's foot. Free of time, never of the map.
  A raised floor takes the place's own word (`names`: the gate's wall-walk, an inn's
  landing, a granary's loft). The plan's travel cannot stand in for it
  (`acts_to_ops.walk_in_place`), the move's tell says where it ended ("up onto the
  wall-walk"), and the read-back asks where in the place the page leaves the player
  (`beat_verify` `height`, finding `beat-height`).
- **The rail opens where the stair arrives**, and both boards draw a gallery's rail on
  its edge rather than through the square in front of it.

### Phase 2 (not built)

- The Climb check onto a crate or cart rolled from the move itself (phase 1 refuses with
  the DC named).
- Breaking, burning, pushing, rolling and toppling fixtures, reading the `breakable`,
  `flammable`, `movable`, `hardness` and `hp` already in the file; a barrel rolled to
  block a stair becoming `blocked` or `difficult` squares on a Strength check.
- A chandelier swing.
- Doors and windows: placed in walls, opening and closing as state.
- The creative +2 from the judge, only for a fixture that exists.
- Low-obstacle cover's 30-foot clause (CRB p.195: only within 30 ft of the obstacle, and
  not when the attacker is nearer it than the target) — the grid's parapets lack it too.
- Steep stairs as difficult terrain (CRB p.415), and "back to the stair" positioning.
- Retiring `judgement._FIXTURES` (above).

**Measured:** the ruling set's position lines (s4-08, s4-09, s4-10, s11-01, s11-07, s7-01, s7-09), re-scored with fixtures present, plus the existing fight benches, which must not move.

## Order and size

1. Part 1, steps 1–2 (cost field and budget). Smallest, and the biggest change to how play feels.
2. Part 1, steps 3–5 (task works, the world's beat, options).
3. Part 2 (fixtures), which also feeds the creative judge.

Each is its own lane off the integration branch, with tests that document the measured defect, the whole suite run, and a live check. The owner tests before release.

## Prior art

- Inform 7 and the Infocom parser for the clause chain (already cited in `gm/sequence.py`).
- Apocalypse World: when the player's move is done, or everyone looks to the MC, the MC makes a move.
- Fate Core: situation aspects and zones, and "established and usable" scenery, already cited in `gm/scenery.py`.
- The engine's own people-keep-their-square ruling for permanence.
