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

## Left open

- `Engine._law_joins` still brings in **every** guard already standing in a town where the
  PC is wanted. Those are residents, not a generated encounter, so this budget does not
  limit them.
- A ship's boarding crew (`Engine`, `min(4, 1 + crew // 25)` sailors) is not budgeted. The
  ship rulings of 2026-11-09 are not built yet.
- Schemes' `bring_in` people and the caravan's own people are single people placed by a
  document, not generated foes, and are not budgeted.
- A companion who is a monster, not a classed NPC, counts at its `level`, not its CR.
- Above CR 20 the budget is clamped to CR 20 (`rung`).
