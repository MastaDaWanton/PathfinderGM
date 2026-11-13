# The encounter budget

Code: `rules/encounter_budget.py`. Tests: `tests/test_encounter_budget.py`.

## Why

Monsters hit at printed strength now (see `printed-attacks`), but the encounter windows were
tuned for when they swung fists. Every picker drew **one creature by its own CR** inside a
window around the PC's level (road and night: CR level-2 .. level+1; forage: the same, +2 for
a guard; openings: a budget of CR = level, with the CRB's small-party step "NOT applied here,
on purpose"). A lone level-1 PC then died to **two CR 1 guards**. That is 800 XP, a **CR 3
encounter**, against a lone level-1 PC. Under the ruling below that PC's APL is -1, so the
fight was APL+4, past epic.

## The owner's ruling (2026-11-13)

1. Price the **whole** encounter by total XP (CRB Tables 12-1/12-2), never per creature.
2. APL is the average level of the PC plus the companions actually with them, adjusted for
   party size by CRB Step 1 (4–5 as is; 6+ +1; 3 or fewer −1), **except a lone PC, who
   counts −2**.
3. Mostly **average** fights (encounter CR = APL). Harder ones only sometimes. Guards and
   lairs may be challenging or hard. Nothing epic unless a document deliberately places a
   boss.

## Research

### Primary rules text: Pathfinder 1e Core Rulebook, "Designing Encounters" (p.397)

Read on the Archives of Nethys, <https://aonprd.com/Rules.aspx?ID=252>. That page cites
*PRPG Core Rulebook* pg. 397.

- **Step 1, Determine APL.** Average the party's levels and "round this value to the
  nearest whole number (this is one of the few exceptions to the round down rule)". "If your
  group contains six or more players, add one to their average level. If your group contains
  three or fewer players, subtract one from their average level." The rules also say they
  "assume a group of four or five PCs".
- **Table 12-1, Encounter Design.** Easy is APL−1, Average is APL, Challenging is APL+1, Hard
  is APL+2 and Epic is APL+3.
- **Step 3.** The CR's XP (Table 12-2) is the budget: "add creatures, traps, and hazards
  whose combined XP does not exceed the total XP budget". Table 12-3 says 2 creatures of one
  CR are worth "CR +2", and "four CR 8 creatures ... are equivalent to a CR 12 creature".
- **CR below 1.** The rules give a progression for an NPC whose CR drops below 1: "its CR
  drops one step on the following progression ... 1/2, 1/3, 1/4, 1/6, 1/8". The CRB does
  not define an APL below 1. Using this progression for an APL below 1 is my extension. The
  forums apply the same progression to APL (see below), but it is not official.
- **How often to use each difficulty:** the CRB page says nothing. I could not find a
  Paizo-published PF1e distribution.

### The 3.5 ancestor: DMG Table 3-2 (could only be partly confirmed)

The 3.5 DMG had a table for how often each difficulty should come up. I could not get the
book's text. One secondary page (cleverfull.weebly.com, "3.5 Edition DMG Table 3-2 Encounter
Difficulty", found by search) gives **10%** easy (EL below party level), **20%** "easy if
handled properly", and **50%** challenging at EL = party level. **I could not confirm the
rest of the table.** I remember it as 15% very difficult and 5% overpowering, but no source
I reached confirms that. A 2013 Paizo thread ("Encounter difficulty repartition",
<https://paizo.com/threads/rzs2q3xm>) asks whether that 3.5 table carries into PF. The one
reply says: "The table doesn't strictly apply, though it probably should." That thread is
only evidence that PF never printed its own table.

Taking the confirmed bands only: the 3.5 book had **half of all encounters at the party's own
level**, and **only 20% to 30% harder**. "Mostly average" sits in that tradition.

### Solo play in PF1e: forum house rules, not official

- "One Character Party", Paizo forums, 2013-06-30 (<https://paizo.com/threads/rzs2pwpb>).
  The opening post proposes "Subtract 1 from the APL for every two characters under 4 (so
  One character is APL-2)", which is the owner's −2. It also cites a tool giving APL−4. A
  reply warns that "The CR system is already just an approximation, and any formula based
  upon it will be an even grosser approximation."
- "Determining CR for a 2 man party", 2014-07-11 (<https://paizo.com/threads/rzs2r96d>):
  "Decrease the CR of encounters by 2, and this should be balanced."
- Search summaries of other Paizo threads mention the 1/2, 1/3, 1/4 progression applied to a
  level-1 solo APL. I did not open those threads, so I cite this as an unverified summary.

### Pathfinder 2e: the per-character budget, and where it breaks

PF2e GM Core, p.75, "Combat Threats" (<https://2e.aonprd.com/Rules.aspx?ID=2716>):

| Threat | XP budget (4 PCs) | Per character |
|---|---|---|
| Trivial | 40 or less | 10 or less |
| Low | 60 | 20 |
| Moderate | 80 | 20 |
| Severe | 120 | 30 |
| Extreme | 160 | 40 |

With fewer than four PCs, the budget drops by the per-character amount for each missing PC.
For one PC, **moderate is 20 XP**: one creature of party level −2. The successor system
lands on the owner's "solo −2". The same arithmetic gives a solo **low** budget of 0 XP (60 −
3×20), so **the published method breaks at one PC**, which is why solo needs its own rule.
GM Core also warns: "Use severe encounters carefully—there's a good chance a character could
die". It reserves extreme for when "you're willing to take the chance the entire party will
die". That is the same shape as "nothing epic".

### 5e: a multiplier for numbers, harsher for small parties, and later dropped

- 2014 basic rules, "Building Combat Encounters"
  (<https://www.dndbeyond.com/sources/dnd/basic-rules-2014/building-combat-encounters>):
  monsters' XP is multiplied by their number, and "If the party contains fewer than three
  characters, apply the next highest multiplier". Several foes against one PC are worse
  than their XP sum. This is the action-economy argument behind `MOST = 3` here.
  The page also says "most adventuring parties can handle about six to eight medium or hard
  encounters in a day". Medium and hard are the routine bands. Deadly is not.
- **What was abandoned.** Sly Flourish's summary of the 2024 DMG
  (<https://slyflourish.com/2024_dmg_encounter_building_versus_the_lazy_benchmark.html>)
  describes its procedure as budget, then "Select monsters with an experience point total
  less than the experience budget". The summary has **no multiplier step**. I could not
  confirm from the 2024 DMG itself that the multipliers were removed.
- The 2025 *Dragon Delves* solo option, the "Blessing of the Sole Champion"
  (EN World, 2025-07-03,
  <https://www.enworld.org/threads/d-ds-new-solo-player-guideline-explained.714138/>),
  **buffs the PC** with temporary hit points and Heroic Inspiration. It does not shrink the
  encounters. The same article says the earlier route, scaled-back companions (Essentials
  Kit sidekicks, expanded in Tasha's), "have not been featured since". That approach was
  abandoned. Commenters call the new rules "soft suggestions, not really playtested".
- *The Solo Adventurer's Toolbox* (Paul Bimler, DMs Guild). Reviews say it has its own
  random-encounter tables for 1 PC with a conversion table. **I could not reach its actual
  budget formula.**

### CRPG conversions: Pathfinder: Kingmaker / Wrath of the Righteous

Owlcat's games keep fixed, hand-placed encounters for a party of up to six, and handle
difficulty with **enemy stat presets** rather than a budget. I found no official Owlcat
statement of what each preset does numerically. Community threads (Steam, space4games)
report that "normal isn't really normal" and recommend turning enemy strength down to get
close to tabletop. That is unofficial and I could not verify it. The lesson I take, with
low confidence: a game that ships harder-than-book numbers by default gets its players
turning them down. Do not bake extra difficulty into the default.

### What could not be sourced

- The full 3.5 DMG Table 3-2. Only the 10%, 20% and 50% bands were confirmed, from a
  secondary site.
- Any Paizo-official PF1e difficulty distribution or solo APL rule. As far as I can find,
  none exists.
- The Solo Adventurer's Toolbox formulas. The 2024 DMG text itself.
- Owlcat's preset numbers.

## The design

- **APL** (`apl`): the ruling exactly, with Step 1's round-to-nearest.
  **Party** (`party_levels`): the PC plus everyone bonded by the `company` op (an effect
  whose origin is `company:<ref>`), standing. Not counted: bought mounts (`bought:`), a
  job's caravan people (`job:`), or an animal companion (a class feature, already in the
  druid's level). Gathering counts the PC at the lower of trade and body level.
- **Below 1:** APL 0 is the CR 1/2 rung, −1 is 1/3, −2 is 1/4, −3 is 1/6, and −4 or below
  is 1/8. A lone level-1 PC's average fight is **135 XP** (one CR 1/3, or two CR 1/8). Their
  hard fight is 400 XP (one CR 1).
- **Fitting** (`fits`): a total spends index *c* when budget(*c*−1) < total ≤ budget(*c*).
  That is Step 3's "does not exceed", plus a floor so that an "average" roll is not really
  an easy fight under the average name.
- **Choosing** (`choose`): a hidden d100 picks the tier from `MIX`. A hidden pick then takes
  one (creature, count) pair whose total fits, with count ≤ `MOST` (3), and only 1 for a
  creature the book calls solitary. If nothing fits, the next **easier** tier is tried. A
  **harder** tier is never tried. Ground with nothing small enough is quiet.
- **Codex people** (`most_of`): a document's or table's count is reduced until it fits the
  rolled budget, never below one, because the words named a person.

## The mix (my numbers; the owner may override them)

| Source | Easy | Average | Challenging | Hard | Epic |
|---|---|---|---|---|---|
| `wandering`: road, night camp, forage creature, a ventured place's inhabitant | 20% | **70%** | 10% | 0 | 0 |
| `guarded`: a guarded find, the watch coming for a wanted name | 0 | **50%** | 35% | 15% | 0 |
| `opening`: a document's staged fight | 0 | **80%** | 20% | 0 | 0 |

Reasoning:

- **Wandering** carries the most weight because it is the most frequent source. The 3.5
  table had half its encounters at party level. I go further, to 70%, because the ruling
  says *mostly* average and a solo PC has no one to absorb a bad night. The 3.5 table's
  harder bands total about 20% to 30%. I keep 10% challenging, and no hard, because a
  wandering monster is not chosen for the story: it should not be the night that kills a
  character. The 20% easy keeps the road from feeling like a gauntlet.
- **Guarded** is the ruling's "guards and lairs may be challenging or hard". Average is
  still the most common single answer (50%). Hard (15%) is roughly the confirmed 3.5 band
  above challenging. The watch's floor is still one guard, so a lone level-1 PC who is
  wanted meets one CR 1 Guard (400 XP, hard) at worst. Never two.
- **Opening** never rolls easy, because a staged attack that is no threat reads as no
  attack. Challenging 20% of the time.
- **Epic is never rolled.** A boss is a document's deliberate choice, not a table's. No
  document path that places a boss exists yet. When one does, it should name its own
  difficulty and not borrow these bands.

Measured (2026-11-13, 300 seeds per cell, forest/hills/desert/grassland/swamp at APL −1, 0,
1, 3 and 5): the landed mix was 66 easy / 202 average / 32 challenging in every cell, with
no fallbacks and no empty draws. Counts were 1 to 3, mostly 1. A forage found a creature on
100 of 100 seeds on all ten land biomes at levels 1, 3, 5, 8 and 12.

## Covered since (2026-11-13, "cover the stuff that isnt covered like the guards")

- **The law.** `Engine._law_joins` and `Engine.rally` (a guard rallying to a struck guard)
  both go through `Engine._law_room`: the guards on the side against the party, the ones
  already there plus the ones coming, are priced by `most_of(..., kind="guarded")` at the
  dearest guard's XP. Never fewer than one (the warrant, or the guard the words struck, is
  the floor); the rest stay in the scene, off the initiative, and are said to hang back
  "shouting the alarm" (`Engine._law_held_settle`, its own outcome at the batch's end). A
  watch already inside the tier's least (average) budget comes whole with no d100 rolled.
  Measured: four watchmen (135 XP each) at a wanted lone level-1 PC joined 1 (15 of 20
  seeds) or 2 (5 of 20); all four did before. Only the guards are priced: the person the
  player struck is who the words named and is not counted against the watch.
  Other law doors read, none brings guards into a fight: `rules/arrest.py` confronts and
  hands a blow to `_law_joins`; `rules/trial.py` holds and judges; the street patrol was
  already budgeted (`ontheway.street`). A fight the GM declares through `begin_encounter`
  names its own sides, which are not second-guessed; only the extra law it draws is priced.
- **Schemes.** A `bring_in` whose side is `them` or `foe` arrives at
  `most_of(...)` of its count (`schemes._hostile_count`): guard and watch roles as
  `guarded`, anybody else as `opening`. A witness, a mourner, or any other side is not a
  fight and comes as written.
- **The caravan.** Nothing hostile exists to budget: a job spawns no ambush (Battle
  Brothers' abandoned lesson, `rules/jobs.py`), its people are the party's side, and the
  only trouble on the way is the road's own roll, which is budgeted. Said in a comment at
  the caravan's mint.

## Danger and how often (volatility on land)

`rules/volatility.py` rates a place 0 calm .. 4 lawless. `volatility.scale(world, *places,
base=...)` multiplies a table's base chance by `FACTORS[rating] / FACTORS[base]`, where
`base` is the rating the table's base was set for (the road, the night, a forage and a
venture: uneasy; the street, measured in towns: settled). Only a rating the world STATES
moves anything: no shipped export carries one yet, so every table rolls exactly as before,
to the dice (`test_nothing_stated_is_the_published_rate_exactly`).

### Research (2026-11-13)

- **Pathfinder 1e has no danger scale.** Ultimate Wilderness p.127 (Archives of Nethys,
  <https://www.aonprd.com/Rules.aspx?ID=2388>): "check for encounters four times per day
  ... with a 20% chance of an encounter each time", and "Feel free to adjust the frequency
  ... as best suits your game." Nothing by terrain or danger. A Paizo forum reply
  (<https://paizo.com/threads/rzs2q1h6>) says the same: "I don't think there's any official
  PF wandering encounter table by terrain". I did not find a GameMastery Guide table for
  this and could not read the book itself.
- **Kingmaker (PF1 AP #31, *Stolen Land*, p.13 as quoted by forum users, not read by me):**
  5% a hex entered, 15% a day or night exploring or camping; *Rivers Running Red*: "These
  chances decrease to 1% per hex or 5% per day ... in a claimed hex"
  (<https://paizo.com/threads/rzs2q0wo>, <https://paizo.com/threads/rzs2ku76>). Tamed
  land at **a third** of the wild's daily rate. Secondhand; unverified against the books.
- **B/X / Old-School Essentials** (OSE SRD mirror,
  <https://digital-gm.pages.dev/docs/ose-rules/adventures/wilderness-adventuring/>):
  "City, clear, grasslands, settled lands: 1-in-6"; "Aerial, barren, desert, forest,
  hills: 2-in-6"; "Jungle, mountains, swamp: 3-in-6", once a day. Settled is **half** the
  ordinary wild, the worst ground **one and a half times** it. This is the cleanest
  published danger ladder found. (The OSE SRD's own page returned an error; the mirror
  quotes it.)
- **AD&D 1e DMG** (forum summary of its population-density rule, not read by me): dense 1
  in 20, patrolled 1 in 12, uninhabited 1 in 10 — densely settled **half** the wilderness
  again. AD&D 2e's DMG instead *raises* the chance by one or two for patrolled and populated
  areas (with prepared tables): more people, more meetings, the opposite axis, which is why
  only the hostile bands move here and travellers do not.
- **Pathfinder 2e** GM Core p.209 (<https://2e.aonprd.com/Rules.aspx?ID=3114>): a daily
  flat check by terrain, plains DC 12 (45%) to desert/arctic/aquatic DC 17 (20%), "On a
  road or river, decrease the DC by 2." A 2.25x spread, by terrain rather than danger, and
  again roads mean *more* meetings, not fewer.
- **What was abandoned:** nothing found. No source I reached moved from a danger ladder to
  a flat rate or back. Ultimate Wilderness's flat 20% with "adjust as suits your game" is
  the system leaving it to the GM, which this app has no GM to do.

### The numbers chosen

| Rating | Factor | Source |
|---|---|---|
| 0 calm | 1/3 | Kingmaker's claimed hex, 5% against 15% a day |
| 1 settled | 1/2 | B/X settled 1-in-6 against 2-in-6; AD&D 1e dense 1/20 against 1/10 |
| 2 uneasy | 1 | the published rate (UW's 20% a watch) |
| 3 dangerous | 1.5 | B/X's worst ground, 3-in-6 against 2-in-6 |
| 4 lawless | 2 | **extrapolated**: B/X's 1-in-6 step once more (4-in-6). No table goes past 3-in-6 |

### What moves

- **The road** (`ontheway.road`): the creature (monster) and weather (catastrophe) bands.
  Travellers and a toll keep their own chance: `_weighed` widens the hostile bands and
  multiplies the check by the new total, so each hostile band's chance moves by exactly
  the factor. Rated by the worse end of a journey leg, or the hop. Measured over 600 seeds
  of a six-hour forest watch: creature + weather 33 calm, 91 uneasy, 159 lawless;
  travellers + toll 50, 45, 49.
- **The street** (`ontheway.street`, base settled): the cutpurse and the trouble (the
  bandits). Over 3,000 hops: 30 at the measured rate, 137 at four times it (a lawless
  town); the press, hawkers, beggars and the watch unchanged.
- **The night** (`ontheway.night`): the whole check, on top of the tent's scale.
- **A forage** (`gathering.bands`): the creature and the guarded find widen, the quiet band
  gives way, a rich find stays 20%. Lawless: creature 36, guarded 14, quiet 30.
- **A venture's inhabitant**: half the time, now a d100 against 50 × the factor (the d2
  that stood there could not move).

## Left open

- The struck person is not counted against the watch's budget: a merchant the player hit
  plus the watch can cost more than the tier. The words named the merchant.
- `rally` of non-law kin (thugs for a thug, bandits for a bandit) is still unpriced.

- A ship's boarding crew (`Engine`, `min(4, 1 + crew // 25)` sailors) is not budgeted. The
  ship rulings of 2026-11-09 are not built yet.
- A companion who is a monster, not a classed NPC, counts at its `level`, not its CR.
- Above CR 20 the budget is clamped to CR 20 (`rung`).
