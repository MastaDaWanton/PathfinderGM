# Stage 4 — one clock, one ticker, and the scene's own stores

The section plan for stage 4 of `docs/compliance-plan.md`. Written before the work, so
the delegation is decided once rather than improvised three times.

## What is actually there (verified, not recalled)

**Six sites move the world clock. Two of them expire anything.**

| site | moves | ticks |
|---|---|---|
| `rules/engine.py:2565` `_op_forage` | up to 18 hours | nothing |
| `rules/engine.py:3664` `_op_advance_time` | any | `tick_conditions` only |
| `rules/engine.py:4425` `_op_rest` | 8–24 hours | `tick_conditions` only |
| `play/views.py:295` resurrection | 7–27 **days** | nothing |
| `play/downed.py:95` waking up | 1 hour | nothing |
| `play/craft_views.py:1086` a crafting session | hours | nothing |

**Five tickers. Four throw away what they ended.**
`Scene.advance_turn` (engine.py:333–350) runs `tick_conditions`, `tick_pools`,
`compulsion.tick` and `_drain_periodic` and discards every return value, then
`tick_standing` whose return it does keep. So in a fight, everything that wears off wears
off in silence.

`_op_advance_time` is the one place that already does it right — it collects the ended
list and puts it in the tell ("Ended: …"). That is the pattern to generalise, not invent.

**Even inside one function the two halves disagree**: in `tick_standing`, an expiring
*manifestation* emits `manifest_ended` and an expiring *ward* is removed silently
(engine.py:442 against 449).

**Three of the four tickers only run inside an encounter**, which is why a compulsion
applied out of a fight lasts until the next fight starts, and a cooldown started on the
last round of a fight never counts down.

## The three substages

**4a — one clock.** `Scene.advance(minutes)` becomes the single door: it moves
`clock_minutes` *and* ticks everything by the matching number of rounds, returning what
ended. All six sites call it. The conversion lives in one place (ten rounds to the
minute), so nobody multiplies by 600 again.

*Known hazard:* a resurrection advances 7–27 days. Ticking that honestly will expire
every timed effect on every actor — which is correct, and is a behaviour change the tests
must state rather than discover.

**4b — one ticker, and expiry speaks.** `Scene.tick(rounds)` runs the actor tickers and
the scene tickers and returns a structured record of everything that ended. The round
rollover and `advance` both call it; the ended list becomes a **tell**, because law 3 says
the narrator may only dress what the engine recorded — a buff wearing off mid-fight is
mechanics, and prose that mentions it without a tell is an outcome-claim. Wards expire
with a record like manifestations already do.

**4c — the scene's stores.** Wards, manifestations, guards, blood pools and compulsions
become effect kinds. The save shape changes with the store **in one commit** (stage 3's
rule), with an idempotent migration and a round-trip over the twelve real campaigns.
`Scene.wards` and `Scene.manifests` are unsaved today and their `from_dict` constructors
have zero call sites, so a restart deletes every standing hazard — 4c is where that closes.

## How the work is split

Implementation cannot be parallelised the way research can: 4a, 4b and 4c all edit
`rules/engine.py`, and two agents in one file collide. So the split is by *kind of work*,
not by substage.

- **Reconnaissance — parallel agents.** Six areas mapped at once (clocks, tickers, scene
  stores, persistence, test surface, sequencing). Done before this plan was written.
- **Implementation — single-threaded, by me.** One writer per shared file, one substage at
  a time, suite green at each step.
- **Test authorship — parallel where the file is new.** A new test file collides with
  nothing, so it can be written alongside the implementation it covers.
- **Adversarial review — parallel agents after each substage lands.** Stage 3's review
  caught three blockers that would have shipped; the same panel runs on 4a, 4b and 4c.
- **Verification — the standing rules.** Suite green; a round trip over the twelve real
  campaigns for anything that changes a save; `prove_build` on the packaged exe at the
  end of 4c.

## What reconnaissance changed about this plan

Six agents mapped the clocks, tickers, stores, persistence, test surface and sequencing
before a line was written. Four decisions moved.

**4a must not loop the per-round work.** `Scene.advance(480)` is 4,800 rounds. Calling
`_drain_periodic` or `tick_standing` once under-resolves; calling them 4,800 times empties
every pool and rolls 4,800 saves. **`advance` ticks EXPIRY; `advance_turn` keeps the
firing.**

**Negative time is an exploit today.** `advance_time.amount` is `int()`-coerced and
unbounded, and `tick_effects` is `e.rounds_left -= rounds` — so a negative advance rewinds
the world clock *and extends every timed effect on every actor*. Clamp at the op and assert
non-negative in `advance`.

**Three ordering traps, each silent.** Foraging stamps herb freshness (`carry(...,
at_minute=)`) *before* the clock moves, so advancing first hands the player up to 48 free
hours of freshness. A crafting excursion computes `market.day_of` before the clock moves,
so advancing first rolls the shelf over mid-purchase. Resurrection writes `pc.hp =
pc.hp_max` before its 9-to-27-day jump, so ticking would leave hp above a reduced max.

**Resurrection has no Engine**, so `scene._dice` is None on that path — `advance` must
guard, as `tick_standing` already does.

**Rest deliberately does not charge the body** (a test pins `fed_minutes` unchanged across
a night), and rest currently ticks only the *resting* actor. Making it tick everyone is a
real behaviour change — correct, and to be named in the commit rather than discovered.

**4b starts by giving the rollover a mouth, not by unifying tickers.** The four dropped
returns become records on the existing `scene.hazards` channel, which already drains to the
transcript — and reusing it sidesteps the Scene-field persistence test entirely. `_ward_tell`
returns `""` for an unknown kind and the view drops falsy strings, so **a new record without
a matching branch is invisible *and* green**: every expiry test asserts the rendered
sentence, never the record.

**The clock ratchet is blind to its own fifth clock.** `test_three_laws.py` matches
`\w+_left\s*-=`, and `tick_pools` writes `pool.cooldown_left = max(0, pool.cooldown_left
- rounds)`. The stage's own success criterion is unmeasured for pool cooldowns until the
regex widens — in the same commit, or 4c can grow a clock the test cannot see.

**4c has an evidence-based order, and one store stays put.** Compulsions first (cheapest,
needs no scene store, and deletes a `_CLOCK_SITES` entry). Wards second — they are unsaved
today, so there is no migration to write and nothing to lose, which makes them the right
place for the scene-side store to be born. Manifestations third and expensive: expiry
through a generic ticker never calls `Scene.lift`, so the fog's squares stay in
`grid.obscuring` forever and the room is permanently blind. Blood pools fourth, as a
manifestation kind rather than a new one. **Guards stay as they are.**

**The real saves make 4c far safer than it looked.** Measured on read-only copies: twelve
campaigns, all `save_version 1`, 28 actors, all *out of combat* — zero guards, zero blood
pools, no wards or manifests ever written, and **not one record anywhere carries a
`rounds_left` clock.** There is nothing timed in the user's data to lose. Three traps remain
regardless: manifestation ids are a foreign key that `Ward.manifest_id` resolves through, so
re-minting them on load silently detaches every area ward; a restored manifestation must not
go through `Scene.place()`, because the grid already holds its squares and `lift` would then
leave them opaque forever; and `Ward.from_dict` has no defaults, so a truncated record raises
inside `Campaign.load` and the campaign refuses to open. `Ward.from_dict` and
`Manifestation.from_dict` have zero call sites in the repo and have never been exercised.

## Done means

- One function moves the world clock and one function ticks it; the law test's
  `_CLOCK_SITES` allowlist shrinks by every entry 4c folds in.
- Nothing that wears off wears off silently — every expiry reaches the player as a tell.
- `Scene.wards` and `Scene.manifests` survive a restart, and the unsaved-field allowlist
  in `tests/test_three_laws.py` loses those entries.
- Twelve real campaigns load with nothing moved that the stage did not name.
