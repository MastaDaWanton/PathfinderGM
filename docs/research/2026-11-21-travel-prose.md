# Travel prose: richer, grounded, and without the numbers (2026-11-21)

Lane feat/travel-prose, for 0.4.9.

The owner asked for two things on 2026-11-21:

- "take a look at the narration that comes out after travelling I think we can afford to
  increase the amount of fluff in the descriptions to make it sound better"
- Later the same day, from a forced-march screenshot: "any numbers and/or game mechanics
  should be kept to the GM section ... all the checks should go in the GM lane and be
  replace by descriptions/ visuals of what those checks represent."

The before and after samples are in `2026-11-21-travel-prose-samples.md`. The bench
numbers are in §4.

## 1. How the travel page was built on 0.4.8

| travel | the door | who wrote the prose | what the prose saw | what else was on the page |
|---|---|---|---|---|
| one hex on the Region map | `play/hex_views._tell` | the consequence call (`prompts.call_two_messages`): "two or three sentences of prose — no more" | the tells, and nothing about the land: no brief, no place, no hour | the whole tell, pasted under the prose as a `consequence` paragraph, with the roll arithmetic |
| a road of days, arrival, a voyage | typed, `/api/say` | the planned narrator (`gm/planned.py`), one act slot | the tells; WHAT IS HERE TO SEE (0.4.7) | nothing; tells are never shown on typed turns |

What that produced:

- **The hex move read as a form.** Two sentences came from a call that had been shown no
  ground, followed by "Eight hours on foot east through the forest, to the forest 48 miles
  east of Branford. You set out in the middle of the day and stop in the evening ...
  Looking over the land (Perception d20 12+16 = 28) ...".
- **The prose made up what it was not given.** On the 0.4.8 baseline, a shabti the tell
  only said was "near the way" became a "stone shabti stands sentinel along the path".
- **Seven days at sea were one sentence.** The sea slot is the act slot. Its only colour
  was WHAT IS HERE TO SEE, which describes the deck the party stands on, not the passage.
- **The see block was wrong for a hex.** Its "close by" is the nearest town's land, and
  a hex 48 miles out is not close by it.

## 2. What the traditions say

The sources were read directly, except where marked secondhand. A second pass checked
this section (§6).

- **The Alexandrian, "Hexcrawl Addendum: Describing Travel"**
  (thealexandrian.net/wordpress/51221).
  - Two failures: long-and-boring (too many badly chosen details) and short-and-boring (a
    generic summary).
  - Describe a vector of travel, not each hex. A vector runs to the next interruption,
    and ending one at every watch is a trap.
  - Layer it: terrain, distance and time; then landmarks; a little texture; one small
    activity that turns the spotlight between companions; then "You've reached [where]…
    now what?"
  - Its worked examples are about three sentences.
  - **Taken:** the order of THE WAY's lines, the companions line, and one passage for a
    whole forced march rather than a line for each hour.
- **Pathfinder Ultimate Campaign, Exploration**
  (legacy.aonprd.com/ultimateCampaign/campaignSystems/exploration.html).
  - What a hex holds should "never be 'nothing'". Any hex can hint at local history,
    such as a long-forgotten village's foundation or standing stones; even a wheat field
    deserves detail.
  - Obvious landmarks are found automatically. Others can be spotted from an adjacent
    hex with an hour of study and a DC 10 Survival check.
  - Its travel-time table, for passing through a hex rather than exploring it, gives 5
    hours a plain hex and 8 elsewhere at 30 ft (already the engine's). Exploring a hex is
    counted in days.
  - **Taken:** colour comes from what the hex and the world hold. **Not taken:** keyed
    roadside finds, because World Bible exports no per-hex detail. A thin hex is a data
    gap (an ask), not something the prose should fill.
- **The Angry GM, "Exploring by the Rules"** (theangrygm.com/exploring-by-the-rules).
  Boring travel gets "boiled down to a single sentence", and interest comes from
  decisions. **Taken:** the beat ends on where you are and what now, which the hand-back
  already does.
  - **Not taken:** weather. The article does use weather, a miserable day that hides
    landmarks and penalises navigation, as a main source of decisions. But the engine
    holds a climate, not today's sky, and prose-gold rule 3 forbids claiming the sky.
    This is a data gap, not a disagreement with the source.
- **The One Ring 2e and Forbidden Lands** (secondhand only: fan handouts and forum
  threads; the books were not reached).
  - A journey is a few discrete events, each with its toll, not a travelogue.
  - One reviewer calls TOR journeys tedious as written.
  - **Taken:** a road of days gets one more line of material, not one paragraph a day.
- **The Alexandrian, "GM Don't List #13: Boxed Text Pitfalls"**
  (thealexandrian.net/wordpress/48312). It warns against boxed text that declares the
  PCs' thoughts, feelings or actions ("Don't tell them how they're reacting to it").
  **Taken:** the body's toll is a fact shown in the body ("your legs drag"), not a mood.
- **Kasner & Dušek, ACL 2024** (aclanthology.org/2024.acl-long.651).
  - More than 80% of open-model outputs held at least one semantic error, by human
    annotation.
  - On Wikidata, the simplest-input domain, unverifiable additions far outnumbered wrong
    facts: about 1.01 NOT_CHECKABLE errors per output against 0.11 INCORRECT. The
    authors read this as "with simpler inputs, the models tend to introduce extra
    information".
  - Across all domains INCORRECT is the larger category (for example Llama 2: 1.57
    against 1.25). So the claim is scoped to thin inputs, which is what a travel slot
    without THE WAY is.
  - **Taken:** this is the lane's premise. More room is only safe with more held facts in
    front of the slot, which is why THE WAY exists and why the budget alone was not
    raised.
- **Goldfarb-Tarrant et al. 2020, content planning** (arxiv.org/abs/2009.09870).
  Choosing the content first and then realising it beat writing without a plan.
  **Taken:** the code picks THE WAY's lines; the model only words them.
- **"Echoes in AI"** (arxiv.org/abs/2501.00273). LLM stories echo the same elements
  across generations. **Taken:** repetition is the model's, so the material turns over
  at the source (least recently used, as `see_lines` already does). What still repeats
  is found in code (`travel_repeats`) and the slot is asked once more.
  - **Not taken:** decoding-time avoidance (Avoidance Decoding, EMNLP 2025). It needs
    logit access, which Ollama does not give. That claim was not verified.
- **The house's own record.**
  - CLAUDE.md: "instruction volume loses to demonstration volume" and "the shape of a
    prompt becomes the shape of the output". Hence two walk demonstrations that differ in
    shape, turned over between moves, plus one road demonstration and one sea
    demonstration.
  - All are synthetic, from no world the game holds, and checked for leaks
    (`demo_leak`).

**Tried and abandoned in the traditions:**

- Narrating per watch or per hex. The Alexandrian calls the per-watch vector a trap.
  Hence one passage per move and one per forced march.
- Boxed text that players skip. This rests on forum reports, not on a designer's
  statement.

Hex-clearing procedures are left off this list on purpose. The Alexandrian (5E Hexcrawl)
says only that they "were once quite common", not that they were abandoned or failed.

The one weather-deck abandonment found (orsvarn.com) is outside hexcrawl practice, and
no source was found showing hexcrawls dropped weather tables.

**Could not source:**

- "one striking detail beats a list" as a published rule;
- AI Dungeon's or Friends & Fables' handling of travel or repetition;
- the official Forbidden Lands and TOR text.

## 3. What was built

1. **THE WAY** (`planned.way_lines`, `way_slot`).
   - Shown to the travel act's slot (a hex move or a journey), in place of WHAT IS HERE
     TO SEE.
   - It is read off the outcome's effects and the world, never the tell's words:
     - the ground crossed, with the world's own phrases for it (the land facts of the
       towns at either end, the comma parts that name that ground: "old-growth deciduous
       forest", "Rugged crystalline plateaus");
     - the wider land's name ("Kaldrimia");
     - the hour the walk ends;
     - the body's strains (`survival.strains`, the one derivation the brief and
       `body_shown` read);
     - a forced march as one fact (`march_line`, below);
     - the ship, at sea;
     - who walks with the party.
   - The ground, the body, the march and the companions are always there. The rest turns
     over, least recently used, as do the world's phrases and the walk demonstration.
2. **Room.** The slot grows by `WAY_EACH` (70 characters) a line, to `TRAVEL_CEILING`
   (620), and is asked for "three to five sentences". The beat budget is unchanged at
   850: the 0.4.7 bench showed a budget alone changes nothing.
3. **The hex move is told the planned way.** `hex_views._tell` builds THE SCENE as a typed
   turn does and hands it to `GMAgent.narrate_outcome(brief=…)`, which writes through
   `planned.write`. That gives the slots, THE WAY, the tells check, the came-out check
   and the groom tail. A planned failure falls back to the consequence call, as before.
4. **Repeats caught in code** (`travel_repeats`). The slot is asked once more, with the
   repeat named, when it contains:
   - a stock travel phrase from a closed list (`TRAVEL_TICS`, which includes the measured
     "silent monuments" and "stands sentinel");
   - a four-word phrase the last beat used;
   - or the last beat's opening three words.

   The remake is kept if it repeats less.
5. **Numbers to the GM's section** (the second ruling).
   - **Where the GM's section is.** There are three candidates:
     - the Rolls panel (`#panel-rolls`) already shows every roll in an outcome's `rolls`,
       label, total and modifiers;
     - `#gmview` is the scheme view behind a house rule;
     - table talk's `record` is a "The record" disclosure drawn under a beat
       (02-state.js).

     The hex move's story beat is now the prose alone. The engine's whole tell (the
     look's roll, the toll, each forced-march check, the XP) rides under it as its
     `record`, and the Perception roll is in the Rolls panel as before. The forage, mine
     and prospect excursion shares the pipe and now does the same: the haul's tally stays
     on the page and the check moves to the record.
   - **The checks become what they meant.** The slot is given the toll as the body's
     strains and the forced march as `march_line`: "the forced march: five hours past the
     day's walking; you held up through all of it; Brakka faltered in hour twelve, left
     fatigued". No figure is in it. It is read off feat/hex-travel-to's `forced_march`
     effects (one a walker an hour, with `passed`, `hour` and `conditions`). So five
     hourly checks are one passage, plus whoever faltered and when.
   - **The look's success** reaches the slot as the tell's own words ("broken walls show
     to the south-west"), and the planned narrator writes no numbers.

## 4. The bench

**Setup.**

- 18 chains, 58 travel beats per arm, played in-process through the real doors
  (`/api/hex/move`, `/api/say`; the scratch driver is pgm-work/travel-bench/bench.py, on
  tools/narration_diag/drive.py).
- Two worlds:
  - the owner's 0.4.4 save (Aurvantis) and three more Aurvantis saves;
  - a fresh Pangrella campaign.
- What was played:
  - **hex:** 8 chains of 4 consecutive moves;
  - **journey:** 6 chains of 3 typed turns, taking the road and then walking on into
    the town;
  - **sea:** 4 chains of 2 typed turns, booking passage and then setting sail.
- The arms ran back to back on master 72d08db0 and on this branch, with the same Ollama
  seed for each call.
- Two blind scorers each scored all 116 items: arms hidden and shuffled, an
  invention/contradiction/omission rubric, and a 1-5 prose score. They agreed on
  has-an-error for 111 of 116 items.

**Mechanical numbers** (pgm-work/travel-bench/measure.py; characters are per beat):

| | hex before | hex after | journey before | journey after | sea before | sea after |
|---|---|---|---|---|---|---|
| prose characters | 283 | 339 | 353 | 370 | 481 | 548 |
| engine-line characters on the story | 397 | 0 | 0 | 0 | 0 | 0 |
| engine share of the story page | 0.58 | 0.00 | 0 | 0 | 0 | 0 |
| figures/mechanics on the story, per beat | 5.25 | 0.00 | 0.00 | 0.00 | 0.38 | 0.00 |
| four-word phrases shared with the last beat | 0.59 | 0.38 | 0.44 | 1.17 | 2.38 | 2.88 |
| same opening as the last beat | 2 | 1 | 0 | 1 | 0 | 0 |
| stock travel phrases (`TRAVEL_TICS`) | 2 | 0 | 2 | 1 | 1 | 0 |
| seconds a turn, mean (median) | 13 (11) | 20 (16) | 56 (44) | 43 (42) | 51 (45) | 45 (45) |

Self-repetition across each whole chain (Salkar et al., `narration.self_repetition`)
rose from 0.043 to 0.066. The world's own phrases recur: "old-growth deciduous forest
of the Faerholt March" on most forest moves, because a land has two or three such
phrases. That is the honest cost of grounding colour in a world that wrote little.
More land words per region would help; this belongs with ask #34's neighbours in
docs/for-world-bible.md.

**Blind scores** (paired by beat, the after-arm minus the before-arm, with 95% bootstrap
intervals):

| | scorer | errors a beat | prose 1-5 |
|---|---|---|---|
| all, 58 pairs | A | 0.64 -> 0.50 (-0.14, -0.36..+0.07) | 2.69 -> 2.95 (+0.26, +0.09..+0.45) |
| all, 58 pairs | B | 0.55 -> 0.48 (-0.07, -0.28..+0.12) | 2.78 -> 3.02 (+0.24, +0.07..+0.43) |
| hex, 32 | A | 0.38 -> 0.28 | 2.78 -> 3.16 (+0.38, +0.16..+0.59) |
| hex, 32 | B | 0.31 -> 0.25 | 3.00 -> 3.28 (+0.28, +0.06..+0.56) |
| journey, 18 | A / B | 1.00 / 0.83 -> 0.72 / 0.72 | +0.11 / +0.22, not significant |
| sea, 8 | A / B | 0.88 -> 0.88 | +0.12, too few to say |

**Reading it.**

- Prose quality rose for both scorers, with intervals clear of zero. The hex move,
  where THE WAY and the planned path both arrived, carried most of the gain.
- Errors did not rise. Both scorers lean lower, but neither interval excludes zero, so
  the honest claim is "the same, possibly fewer".
- One bias favours the before-arm on omissions: its pasted engine block made every fact
  "present" on the page.
- Most remaining errors are not travel prose. They are people the arrival and passage
  beats bring on (a market keeper, a harbourmaster with a rumour), which is the town
  beat's own matter and aside slots, unchanged here.
- Travel-specific slips seen in the after-arm:
  - a world phrase used as a place ("the dense thicket of the western spine");
  - "twenty-four miles of Fizspark", with the bearing dropped;
  - a stopped-short road told as standing at the gate.
- Seconds: the hex move costs about 7 s more a move (16 s against 11 s median), for the
  planned slots and the tells check. The journey and the sea are unchanged; the spread
  there is the shared GPU.

## 5. Owner calls made by default

1. **The Perception figure leaves the story** (formerly "(27)", then "Perception d20
   12+16 = 28").
   - It is in the Rolls panel, the GM's section where every roll already lives, and in
     the beat's record. The second ruling says so; recorded here because the brief asked
     for it to be the owner's call.
   - Recommendation: keep it off the story.
2. **The GM section is the beat's own folded record, plus the Rolls panel.** It is not a
   new pane.
   - The record is the disclosure table talk already uses, so no new UI was built.
   - The alternative, a GM-lane column of its own, would be a layout change, and the
     look stays.
3. **The excursion's check moves to the record; the haul's tally stays on the page.** A
   count of what was gathered is the haul, not a check.
4. **What was left alone, with counts.** Measured over all 12 of the owner's
   campaigns, 1,484 GM beats:
   - **343 bench and craft lines** with their d20 and DC ("Ground Henna: spoiled (d20
     1+4 = 5 vs DC 10)").
   - **35 XP award lines.**
   - **31 tasting and survival-check lines.**
   - **1 bleeding line.**
   - **3 hex lines.** These are now fixed.
   - Zero planned narrator beats carried a figure.

   The bench lines are each bench's own door, and that is a lane of its own (the five
   crafts). A fight's numbers already sit in the Rolls panel and the fight's own lines,
   unchanged.
5. **Weather.** None was invented. The engine holds a climate, not a day's sky, so THE
   WAY gives none. A journey's own weather event reaches the prose as its tell.

## 6. Second pass

A critic re-read the primary sources for §2. It found:

- no misattributions;
- five places that needed tightening, all corrected above:
  - Ultimate Campaign's 5 and 8 hours are its travel-time table, not exploration, and
    "never nothing" is not tied to plains;
  - Kasner & Dušek's 1.01 against 0.11 is the Wikidata domain, and across all domains
    INCORRECT is the larger category;
  - the Alexandrian's 5E Hexcrawl says hex-clearing was "once quite common", not that it
    was abandoned, so it is off the abandoned list;
  - GM Don't List #13 does not say "never";
  - the Angry GM uses weather as a main source of decisions. It is left out here for want
    of data, which is now said.

The One Ring, Forbidden Lands and Avoidance Decoding stay marked secondhand or
unverified.
