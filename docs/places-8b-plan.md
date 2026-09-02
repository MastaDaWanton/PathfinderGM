# Places 8b–8e — one coordinate, and everything that fell out of holding two

The working plan for the second half of `docs/places-plan.md`. Written after a
five-tradition primary-source sweep (Inform 6/7's WorldModelKit, DikuMUD/CircleMUD's
handler.c, LambdaMOO's built-in `move()`, Evennia's `move_to`, Bevy 0.16's `ChildOf` /
`Children` and Godot's `reparent`), six code maps covering every one of the 171
production reads of `scene.actors`, and a critic pass over both.

## What the sweep settled

Every tradition holds the relation **on the contained thing**, never on the container,
and derives "who is here" from it:

- Inform 6: `parent` on the object; contents enumerated by walking `child`/`sibling`.
  DM4 §3.1: "the parent of an orphan would be nothing". "Location of X" is *computed*
  on every call (`LocationOf` climbs the tree; WorldModelKit §3), with exactly one cache
  — the player's own room, `real_location`, rewritten only by `PlayerTo`, "the player
  object can only be moved by this routine: this allows us to maintain the invariant"
  (WorldModelKit §13).
- Bevy 0.16: `ChildOf(Entity)` on the child is documented as 'the "source of truth"
  component'; `Children` on the parent is a `RelationshipTarget` maintained by hooks and
  "should not be directly manipulated to avoid desynchronization". Bevy shipped the
  two-sided design through 0.15 (both `Parent` and `Children` real components, kept
  level by commands) and **replaced it** in 0.16 because writing either side by hand
  "may result in hierarchy invalidation" — they shipped a polling diagnostic to catch
  the corruption before they gave up on the design.
- Godot: a node's parent is the one relation; `reparent()` was added in 4.0 because the
  hand-rolled `remove_child` + `add_child` lost the global transform and the owner.

And on the two questions the code maps forced:

- **Removal is not a move.** Inform's `remove X` "only takes an object out of the tree
  for a while but keeps it in existence" (DM4 §3.4) and refuses to remove the player;
  Bevy's despawn cascades and strips the relationship from every source. Two doors.
- **Time passes for the absent.** Inform's every-turn rules run over off-stage objects;
  nothing in any tradition freezes an object because the player is not looking at it.

## The four decisions the maps forced

**1. Refs are minted once and never recycled.** Five copies of "the lowest `cN` not in
`scene.actors`" exist (`bestiary._next_ref`, `engine._projected_refs`, and three in
`gm/judgement.py` at 583, 687, 967, 1345). Under containment an actor in the next room
is not in the view, so every copy would re-mint a ref a living creature still wears —
two bodies, one key, across zones, positions, initiative, sides, guards, wards, pools,
spawn_feet, fallen, reacted, cast[].ref and the watcher's process-global `_GARNISHED`.
The maps found **five per-ref tables already poisoned by recycling today** (`spawn_feet`
documented at engine.py:855, `fallen` leaked by three of the four depart doors, `pools`
never cleaned, `attacked` cleared only by end_encounter, the market's stall key folding
the merchant's ref). Minting against the full store retires the whole class. One
function, `bestiary.next_ref(scene)`, and the other four copies call it — CLAUDE.md's
grep-for-every-copy rule, applied. `test_a_departed_creature_takes_its_spawn_distance_
with_it` asserts recycling as fact in its docstring and is rewritten to pin the
opposite.

**2. The world clock ticks everyone the campaign holds.** `Scene.advance` (the "one
door" for time) and the round rollover iterate `self.actors`. With a here-only view, an
NPC in the next room keeps every timed buff through an eight-hour night and a dying man
the party walked away from neither bleeds nor stabilises — the survival module's own
failure ("the clock moved and the body did not know"), for the absent. Both iterate the
full store. The round rollover's *hazards* (`tick_standing`) stay scene-local: a cloud
in this room does not burn a man in that one.

**3. Bodies stay where they fell, and age out wherever that is.** Death does not move
an actor — `tidy_the_fallen` sees the corpse through its two-turn grace because the
grace is *why* it is still in the view (loot, heat, the finishing-blow check, the
dead-men-walking cut all read it there). But the ageing loop runs over the full store,
so a body the party walked away from still leaves after its grace instead of
accumulating in a room nobody will re-enter. The three shedding predicates —
`tidy_the_fallen` (narrow `state.down.fallen`), `leave_behind` (whole `is_down`
family), `_op_travel` (`is_down` plus the `with` exemption, and the only one that
departed the dying *unresolved*) — collapse to two rules with one owner each:
*ageing* (a body on the floor leaves after grace, `tidy_the_fallen`, full store) and
*coming along* (only the PC and the named escort move; everyone else stays, with the
dying resolved before the party is out of earshot). `leave_behind` and `clear_cast`
stop departing anybody — walking out of a room is a `travel`, and the room keeps its
people because that is what a room is.

**4. The world's biome is the root; the place carries it; the scene stores nothing.**
`spots_for(location, terrain=scene.biome)` seeds the place list off the biome, and 8c
wants the biome read off the place — a loop. The root is `biomes.from_world(world,
location)`: a fact about the location entity, read at place generation, never stored on
the scene. Open ground is a *region* of the location keyed by biome — the party
"travels to the forest" and stands in `{location}~forest:the-approach`, a wild place set
with that terrain. `scene.biome` becomes a property, `here().terrain`, and the eleven
sites that read it (foraging tables, hardship, the five bench filters, `_at_market`, two
injector equalities, the raw token in three prose strings) get the same canonical enum
string they get today from the same one attribute. Two copies of the world-default rule
(`campaign.py:153` and `:362`) become one: a new campaign is placed, not biomed.

## The shape

```
Actor.at: str                       # place id; written ONLY by Scene.move / Scene.add
Scene.people: dict[str, Actor]      # the store: everyone the campaign holds
Scene.actors -> Mapping[str, Actor] # DERIVED: people whose .at == scene.at; read-only
Scene.at: str                       # the party's place (the PC's .at, one writer)
Scene.biome -> str                  # DERIVED: here().terrain
Scene.move(ref, place_id)           # the one mover: side tables cleaned, .at stamped
Scene.remove(ref)                   # the one destroyer: move-clean + del people[ref]
bestiary.next_ref(scene)            # the one minter: against people, monotonic
```

`Scene.actors` is a read-only `Mapping` view — `.items()`, `.values()`, `.get`,
`[ref]`, `in`, `len` and iteration all work, which is the whole read surface the maps
found. Assignment, `pop`, `update` and `del` raise, so the five write sites cannot keep
working by accident: `Scene.add` writes the store; `Scene.depart` becomes `remove`;
`promote_cast` loses its `update` fallback; `Campaign.load` fills the store; the
resurrection path in `views.py:310` goes through `remove` (it bypassed `depart`'s
side-table cleanup entirely, which the map lists as a sixth writer).

`Scene.pc()` reads the **store**, not the view — defining "here" as the PC's place and
the view as "actors in the PC's place" is circular otherwise. `scene.at` and the PC's
`.at` have one writer: moving the party is `move(pc.ref, place)`, which sets both.

`Scene.move` is `depart` without the `del`, plus the four tables `depart` leaked
(`fallen`, `pools`, `attacked` entries naming the ref, `manifests` owned by it). An
actor's tactical state — zone, square, initiative slot, side, reactions, guards, wards
— is meaningless outside the place it was in, so a move drops all of it. Moving the PC
mid-encounter is refused as it is today (travel ends the fight); the difference is that
`_op_travel` now **settles XP before ending it** — the map found it calls
`end_encounter` without `_settle_xp`, so a fight you walk out of pays nothing, silently.

`snapshot`/`restore` are unchanged: the store is an instance attribute in `__dict__`
and the view is a property with no cache.

## Persistence

The save writes `people` (every actor, each with `at`) instead of `actors`. Load reads
`people` and, for a save written before this, `actors` — healing a missing `at` to the
scene's `at`, and a scene with `at == ""` to the first place of its location (the same
courtesy `Campaign.biome` extended to saves written before biomes existed). The stored
`biome` is read once at load to choose a wild region when an old save had the party on
open ground, and never written again. `to_dict` gains `at`; the roster mirror
(`roster.py`) receives it and `Scene.add` overwrites it on the way into a new campaign,
so a place id never travels between worlds.

## The validator

`_known` silently changes meaning from *exists* to *is here*, and its refusal says
"unknown ref — create them first with spawn" — which under containment invites the
model to spawn a duplicate of the merchant standing in the next room. Two branches:
a ref nobody holds ("unknown ref … spawn"), and a ref somebody holds elsewhere ("c3 is
at the tavern, not here; travel there or leave them out of it"). Ref minting for the
schema's `enum` uses the store, so the model is never offered a ref it cannot act on.

## 8c — terrain is derived

- `Engine.places()` derives terrain from `biomes.from_world` for the settlement set, and
  from the region key for a wild set. `gm/prompts.py:655` is a second copy of this
  derivation and goes; the brief calls `engine.here()`.
- `_op_travel` with a `biome` and no `place` resolves to the wild region's first place;
  with a `place`, to that place. `scene.at` is the only thing it writes. The `moved`
  test is a place comparison, not a biome one.
- `Campaign.biome` stops healing a stored field and returns `scene.biome`, the property.
  `new_campaign` places the party at the first place instead of writing a biome.
- The twenty-four test sites that assign `scene.biome` become place assignments; a
  helper `tests/_places.py:stand_on(scene, biome)` keeps them one line each.

## 8d — one writer for where

`thread["where"]` has three writers in `update_thread` (2148, 2170, 2174), all regexes
over the player's sentence, and two readers: `thread_brief` ("Both of them are ALREADY
in {where}") and `views.py:1137`'s `already_there`. The brief therefore carries two
place assertions from two sources in one prompt. The writers go. Both readers take the
place from `Engine.here().name` — with the same `the`-stripping `already_there` already
does, because generated place names carry the article and an unmatched pattern silently
never rewrites. The cast ledger is cleared by `Scene.move` of the PC, not by the
`_WALKS_AWAY` regex alone: the map found that a model-proposed `travel` left promoted
civilians on a ledger the brief still printed as "ALSO PRESENT".

## 8e — the ratchet

`tests/test_three_laws.py` gains a spatial-authority test with these assertions, each
naming its measurement:

- Nothing writes `scene.biome` or `thread["where"]` (AST over `rules/ gm/ play/`).
- `Actor.at` is assigned in exactly two places, `Scene.add` and `Scene.move`.
- One ref-minting function; the four former copies are gone (AST: no `while f"c{n}"`
  loops outside `bestiary.py`).
- `Scene.move` refuses a place id that `places()` does not know — a runtime assertion,
  because a place that did not come from the registry is the free-text `spot` coming
  back through a side door.
- Every per-ref side table the maps listed is cleaned by `move` — a probe that spawns,
  arms every table, moves, and asserts each one is empty of the ref.

## Amendments from the adversarial review

Four refuters attacked the plan above through four lenses (the mover, the ref namespace
and persistence, the biome root, the where-writer and validator). What follows is what
broke and what the plan now says instead. Each is checked against the code.

**Terrain lives inside the place id, for every place.** `Scene.biome` as `here().terrain`
cannot be a Scene property: `here()` needs `places()`, which needs the world, and Scene
holds no world by design. So the id carries it — `{location}~urban:the-market`,
`{location}~forest:the-approach` — and `Scene.biome` is a parse of `Scene.at` with no
lookup at all: `rules.places.terrain_of(at)`. The settlement set's terrain is `urban`
**by construction** whenever `places._settled(location)` holds; `biomes.from_world`
supplies nothing to a settlement place and is consulted only when there is no entity
to ask. Any canonical biome names a region; the region set is derivable from the
location id and the terrain with no world, which is what lets a world-less test engine
stand on the forest. One derivation, `places.for_scene(location, at, hint)`, serves the
engine and the brief; the copy at `gm/prompts.py:655` goes.

**`Engine.places()` returns the settlement set and the current region's set together**,
so "return to the market" resolves from the forest. Region places share the `_WILD`
names, and only one region is ever current, so `find()` stays unambiguous.

**A travel whose biome equals the ground already underfoot is a no-op**, tell and all;
one whose biome equals the settlement's own terrain resolves to the settlement —
`urban` never mints a region. Three production paths send `urban` back to town (the two
injectors and the bench picker) and every one of them was going to teleport the party
to a region called urban.

**Refs need a high-water mark, or "monotonic" is a lie.** A lowest-free scan over a
store that `remove` deletes from is recycling by another name, and the ageing loop
deletes every corpse after two turns. `Scene.minted: int` lives in `__dict__` (so a
refused turn that minted a ref legitimately reissues it), is saved and loaded, and heals
on an old save to the highest `cN` the save holds. The one minter is
`bestiary.next_ref(scene, taken=())`: projection passes the refs it has already
projected and advances nothing; only `Scene.add` bumps the mark. The 8e ratchet searches
for the `f"c{...}"` pattern outside `bestiary.py`, not for a loop shape.

**The schema enum stays the view.** The sentence "ref minting for the schema's enum uses
the store" was backwards: the enum is what keeps the merchant in the tavern out of
`actor`/`target` at the sampler. The store is consulted only to mint and to project.

**Guards and wards are relational, not tactical.** `end_encounter` deliberately keeps
`scene.guards`, and a standing "X interposes for the PC" survives a fight today. A guard
is cleaned when its two ends are in different places **after every move of a travel has
happened** — the PC, then the escort — not inside each per-ref `move`. A ward with an
owner travels with its owner (it is the teeth of something on the body); an area ward
(owner `""`) is place-bound. `Scene.tick_effects` looks a `stops_with` ward's owner up
in the store, or an owner in the next room reads as cured.

**Pools and manifests are place-bound and neither door touches them.** Blood on the
floor stays on the floor of the room it was spilled in — `_op_spend_pools` filters by
owner and reads the view, so a bender who walks out cannot reach it and a bender who
walks back can. Manifests expire on their own clock. The "four tables depart leaked"
sentence above is wrong by two: `move` and `remove` clean `fallen` and the `attacked`
entries naming the ref, and nothing else that was not already tactical.

**A compulsion travels with the compelled; `remove` lifts it.** `compulsion.add(target,
by=towards)` stores the compeller's ref on the target's own `ActiveEffect`, outside every
scene table. A move does not touch it, and `remove(ref)` walks the store lifting every
compulsion `by` that ref, so a compeller who ceases to exist takes the pull with them.

**The mid-encounter rule, stated correctly.** Travel mid-fight is *accepted* today and
ends the encounter; the plan said refused. `_op_travel` orders `_settle_xp()` →
`end_encounter()` → the moves, and its tell carries the XP line, so a walked-out fight
pays what it pays out loud. `Scene.move` of the PC refuses mid-encounter as a guard on
every *other* caller, and `remove` refuses the PC as `depart` did.

**`with` gets a namer, a validator and a sentence.** It is read at one production line
and written by none — no prompt teaches it, no injector writes it. `_check_refs` now
validates `params.with` against the view; `_op_travel` resolves names to refs before any
move; the travel paragraph in the briefing names it.

**The "not here" refusal does not invite a repair the validator will refuse.** "Travel
there" in the same list fails the next intent's ref check. The sentence is: "c3 is at
the tavern, not here. Leave them out of it this turn." The combat panel maps the same
refusal to a player-readable "That person is no longer here."

**Nothing moved the PC on "I leave the tavern".** `inject_travel` refuses to guess a
place and `declared_ops` therefore never forces the op, so a place-less departure under
the plan left the merchant in view — a regression from today's regex belt. Now
`declared_ops` declares `travel` whenever `_WALKS_AWAY` matches and the location has
more than one place, and the schema's `must_contain` makes the model choose a
destination from the brief's list at the sampler. The regex path keeps a residual
contract: `leave_behind` resolves the dying and departs nobody; `clear_cast` empties the
ledger and departs nobody. `tests/test_judgement.py:1485` pins the old departing job and
is rewritten to pin the new one.

**`here` is computed once, on the Engine, and passed down.** `thread_brief` and
`already_there` cannot reach a world. `scene_brief(..., here=, known=)` takes them from
its four callers; `thread_brief(scene, where=)` and `views.py:1137` get `here.name`
from the same object. On the turn the party *arrives*, `here()` is already the
destination when the prose runs, so `already_there` would rewrite the arrival beat —
the rewrite is skipped when any outcome that turn is a `travel` that changed place. The
thread sentence asserts only what the engine knows and is suppressed for the exitless
no-location fallback. `_THREAD_WHERE` survives as the subject trimmer at
judgement.py:2141; only the three `where` writes go.

**Persistence, precisely.** `from_dict` reads `at` (default `""`); the load heals an
actor only when the saved dict has **no** `at` key. `SAVE_VERSION` becomes 2 and the
`actors` reader stays for version-1 saves. The heal runs after the Campaign is built,
where the world is: resolve `scene.at` first — `at == ""` with the stored biome equal to
the settlement's terrain (or empty) is the settlement's first place; any other stored
biome is that region's first place — then stamp every unplaced actor with the resolved
id. `new_campaign` places the scene **before** adding anybody, or the opening companion
is out of view on turn one. `Scene.add` stamps `scene.at` unconditionally, so a roster
sheet's foreign place id never enters a new campaign; its grid keyword `at=` is renamed
`square=` so the field and the argument cannot be confused.

**The five test sites that write `scene.actors` directly** (`test_foraging.py:479`,
`test_watcher.py:197`, `test_judgement.py:856`, `test_trade.py:913/919`) are rewritten
through `add`/`remove`.

**Left as is, on purpose.** Resurrection walks the store and removes every NPC — a clean
slate, which is what the dict meant when it was everyone. A stabilised escort cannot be
carried and ages out where it lies, as `leave_behind` already did to it. The watcher's
process-global `_GARNISHED` stops being a poison once refs are never reused.

## Refused

- **A cached `contents` list on the place.** Bevy's 0.15 design, abandoned for exactly
  the desynchronisation a hand-maintained second copy invites. The view walks the store
  on every call; at a dozen actors the cost is nothing, and there is no cache to
  invalidate in `restore`.
- **Keeping ref recycling and adding a "retired refs" set.** A second table to keep
  level with the first, which is the design being removed.
- **Freezing time for the absent.** The traditions do not, and the survival module
  has already paid for the version that did.
- **A per-place cast ledger.** The ledger is prose-people the narrator introduced *here*;
  moving clears it, which is what walking out of a room does to the people in it.
