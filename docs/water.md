# Water

`rules/water.py`, `rules/biomes.py`, `Engine.breathe`, `Actor.water_row`,
`tests/test_water.py`. Written 2026-09-16.

## The gap

**The engine had no water.** Fourteen terrains, not one of them wet: `aquatic`,
`underwater`, `river` and `lake` all resolved to `coast`, so the sea was the sand beside
it. Three consequences, all of them measured rather than assumed:

- **468 creatures lived on a beach.** A shark's Environment line reads "any ocean" and the
  only word this app had for an ocean was `coast`. Re-tagged, `water` now holds 359
  creatures — every one of them a *stated* habitat rather than an inference — and `coast`
  drops from 1,100 to 632.
- **Two race traits could never work.** `docs/race-cues.json` published *"a swim speed: the
  engine has no water"* as the reason, and that file goes to World Bible: an author was
  told, in as many words, that a trait they can write reaches nothing.
- **There was nowhere to drown.** The one death in the game that arrives on a schedule
  could not happen.

## Two terrains, not one

`water` is a surface. You can breathe, you have improved cover from anyone on the shore,
and you are swimming or you are wading. `underwater` is below it: no air but what you
brought, total cover, fire does not burn.

Diving is a **move between two places**, which is the shape a storey already has — a lake
that matters is two places and a lake that is scenery is one. Both are `vertical: none`
with nothing blocked and nothing difficult, which is the honest answer: the whole surface
of a lake is one height, a ledge in open water is a thing nobody can point at, and water
is not rough going the way scree is. It is a different way of moving altogether, and what
that costs is the table below rather than a square on a map.

## The table is the whole design

Core Rulebook, Table 13-7. It does not ask what you are doing. It asks **what you have**:

| row | what it is | slashing / bludgeoning | piercing | speed |
|---|---|---|---|---|
| `free` | freedom of movement | — | — | — |
| `swimmer` | a natural swim speed | −2, half damage | whole | whole |
| `swimming` | a made Swim check | −2, half damage | whole | a quarter |
| `footing` | on the bottom, weighed down | −2, half damage | whole | a half |
| `off-balance` | none of those | −2, half damage | −2, half | whole |

`off-balance` also gives every opponent **+2 to hit you** and takes your **Dexterity off
your AC**. That row is what happens to an armoured character who goes over the side, and
it is the whole difference between a fight in water and the same fight in a blue room:
you are not harder to hit, you are easier, and your sword does half.

A weapon that can do either kind — "slashing or piercing" — uses the half that still
works. That is a reading rather than a printed rule, and it is written down here because
somebody will want to know whether it was a decision.

## How it lands

Nothing here is stored. The ground is inside the place id, so `Actor.water_row()` parses
`~water:` off its own `at` and needs no world to know it is in the sea — the same
arrangement that lets `scene.biome` be derived rather than kept.

- **The attack penalty rides the one funnel**, as a modifier named "the water", so it is
  itemised beside every other modifier and a player can see why the number is the number.
  It cannot ride a condition's flat `attack` the way `shaken` does, because the book
  scopes it by damage *type*.
- **The damage halving is not a modifier** and is not pretended to be one: a modifier is a
  number added to a roll, and this is a rule about the roll's result. It is applied where
  the weapon's type and the swinger's footing are both known, and never below 1 — a hit
  that lands is a hit.
- **The defender's floundering is read off the defender**, where cover already is.
- **The breath is a counter and the drowning is a check**, split exactly where
  `Scene.advance` says they split: *"the COUNTERS move here and the CHECKS do not"*. The
  counter moves on the same clock as hunger; `Engine.breathe` rolls.

## Drowning

Twice your Constitution in rounds. Then a Constitution check each round at DC 10, rising
by one every round. On the first failure: unconscious at 0. The next round: dying at −1.
The round after that: dead. No save interrupts the last part — that is the book's own
design, and what the engine owes the player is that the schedule be **visible**, so every
rung of it tells. A schedule the player cannot see is a trapdoor.

Surfacing resets it, because breathing is what holding your breath stops being.

A creature that breathes water is not drowning in it: `amphibious` on a race card, the
`aquatic` subtype in the bestiary, both asked through the vocabulary.

## Found while building this

`apply_hp_state` cleared `dying`, `stable` and `unconscious` on death and never
`disabled` — so a corpse could still be "conscious, and a standard action costs a hit
point". Nobody had ever found it because most deaths do not stop at exactly 0 hit points,
and drowning walks a body down the ladder one rung a round.

## Still open, and deliberately

These are in the module as constants with nothing reading them yet. They are listed here
rather than left to be discovered, which is the bargain every other ledger in this repo
makes:

- **Ranged attacks through water** (−2 for every 5 feet crossed; thrown weapons useless).
  The number is in `water.RANGED_PER_5FT`; the attack path does not ask it yet, because
  "how much water is between these two" is a question about the grid and the grid has no
  notion of a water column.
- **Cover from the shore** (+8 AC and +4 Reflex at the surface, total cover below). The
  numbers are there; `rules/position.py` owns cover and does not read them.
- **Fire spells underwater** (caster level check, DC 20 + spell level) and **casting while
  you cannot breathe** (concentration, DC 15 + spell level).

## The Swim check, in every water (2026-11-13, widened 2026-11-14)

`Engine.swim`, `Scene.afloat`, `water.roughness`, `tests/test_swim_checks.py`.

- **One question: `Scene.afloat`.** True on any square of `Grid.water` and anywhere in a
  `water`/`underwater` place the party is in. `fixtures.type_the_ground` makes every open
  square of a wet place `Grid.water`, so a lake moves like the sea past a rail (a quarter
  of your speed a move, the move refused after a failed check) and the board's sea
  squares (a ship's side, the docks' harbour) are the same water they were. A wet place
  with no board laid still swims. Standing water (the swamp's `water` fixture, difficult)
  is wading and asks no check: CRB p.427, a shallow bog is difficult terrain.
- **Below the surface** (`underwater` ground) a made check swims on under and a bad
  failure sinks; nothing "fights back up to the surface", because coming up is a move to
  the place above, and the breath clock is the ground's own.
- **How rough** (`water.roughness`): a storm on the swimmer (`weather.storm`) is stormy
  (DC 20); otherwise the place's own `play.places[]` row may say `"water": "rough"` or
  `"stormy"` (World Bible ask 17); otherwise calm (DC 10). CRB Aquatic Terrain: "Fast
  rivers are always at least rough water (Swim DC 15), and whitewater rapids are stormy
  water (Swim DC 20)"; placid rivers, lakes and the sea are still water. Wind is not
  read: no wind or storm table in the CRB sets a Swim DC. Floods and currents are read
  since 2026-11-15, from the place's row (below).
- **The cadence.** The CRB asks once per round and has no per-minute check (Swim and
  Aquatic Terrain, read 2026-11-14 on d20pfsrd and legacy.aonprd.com; a "once a minute
  out of combat" rule could not be sourced). It does let you take 10 when not threatened,
  "You can't take 10 on a Swim check in stormy water". So out of a fight and out of a
  storm the swimmer takes 10, which comes out the same every round of the beat, and an
  unchanged success is told once; in a fight or in stormy water the d20 is rolled once a
  beat. Since 2026-11-15 taking 10 is used only where it makes the DC. A swimmer whose 10
  fails rolls, because nobody chooses to fail (`Engine._swim_margin`).

## Long swims, currents, floods and armour (2026-11-15)

Read before building: CRB Swim (d20pfsrd), Aquatic Terrain and Water Dangers
(legacy.aonprd.com Environment, aonprd.com Rules ID 336).

- **The hourly check.** "Each hour that you swim, you must make a DC 20 Swim check or take
  1d6 points of nonlethal damage from fatigue." It is a Swim check in the book's words, not
  a Constitution check. One copy, `Engine._an_hour_swum`, is used by the water beside a
  ship or in a lake (`Actor.swum_rounds`, a counter `Scene.advance` moves beside the
  breath's; `swim` asks it per 600 rounds), the swim out to a ship lying off, and a wreck.
- **Currents** (`water.current`, a place row's `"current": "fast"|"rapids"`, ask 23).
  "A DC 15 Swim check or a DC 15 Strength check to avoid going under"; the swimmer uses
  whichever is better. On a failure, 1d3 nonlethal (rapids, the rocks and cascades: 1d6
  lethal). A fast current makes the water at least rough and rapids stormy. The book's
  10-90 ft a round downstream is told and not moved, because the board has no downstream.
- **Floods** (`"flooded": true`, ask 23): one category harder (`water.HARDER`). Nothing in
  this app floods a river by itself.
- **Armour.** A heavy-armoured swimmer going under in a calm lake is book-correct: Swim
  takes the armour check penalty, and Water Dangers says "armor or heavy gear makes any
  attempt at swimming much more difficult". Every failure the penalty caused (it failed,
  and would have passed without it, `water.armour_is_why`) now says so: "Their armour
  drags at them."

## Not this, and not next

Over-water travel and ship-to-ship fighting are a separate piece, ruled on 2026-09-16:
ships close over a handful of rolls and the fight happens on the deck. The reasoning is
recorded where that work lands, and the short version is that Pillars of Eternity II
shipped text-based naval combat that reviewers called the worst in any RPG — no
orientation, tactically trivial, and always a prelude to boarding anyway. The boarding is
the game.
