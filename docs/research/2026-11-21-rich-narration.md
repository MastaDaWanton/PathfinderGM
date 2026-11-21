# Rich narration out of fights (feat/rich-narration), 2026-11-21

This note records the owner's ruling (2026-11-21) to ship the Rich-N arm of the
richer-prose bench as the default out of fights. Fights keep base narration: the Rich-F
arm waits for a verb fix and a monster bench.

Sources:
- the research and its citations: `C:\Users\natha\pgm-work\richer-prose-paths.md`;
- the measurement: `C:\Users\natha\pgm-work\richer-prose-results.md`;
- the bench code: branch `exp/richer-prose` (b2c62f6a, 7b3569d6), which is left untouched.

## What is shipped, and the prior art behind it

- **WHAT IS HERE TO SEE beside the beat's first act slot** (`planned.see_slot`). It shows
  two of the brief's own place lines, chosen least recently used, then the light when it
  is poor, then the hour.
  - The descriptive facts were already in the brief, but in the middle of an ~11k-character
    system prompt. Liu et al., "Lost in the Middle" (TACL 12, 2024), measured U-shaped use:
    the middle of a long context is used least.
  - SillyTavern's Author's Note docs: "The closer the Author's Note is to the bottom of
    the prompt, the more impact it has".
  - Kasner & Dušek (ACL 2024, arXiv 2401.10186): sparse input invites invention. The cure
    is more held facts, not looser rules.
- **One synthetic demonstration**, from another world, with a closed word list checked in
  code (`demo_leak`).
  - CLAUDE.md: instruction volume loses to demonstration volume.
  - narration.py `MIN_SCENE_CHARS` note: realistic examples were copied as furniture, so
    the demonstration is synthetic and leak-checked, as `beat_verify` does for its own
    readers.
- **`BEAT_BUDGET` 650 → 850, and the act slot grows by 70 characters per line shown** (A7).
  - Kasner again: length without facts is invention; length with facts is richness.
  - The budget alone changed nothing in 2026-10-09 (1800 → 1400).

Measured (105 paired non-fight beats, three blind scorers plus an adjudicator):
- 406 → 478 characters a beat (+71, CI +56..+87);
- errors/beat 0.067 → 0.067;
- invented scene content 0.343 → 0.352 (not significant);
- prose 2.96 → 3.02 (not significant);
- no added seconds.

## Left out, on purpose

- **The bench's environment switch.** Rich-N is now the default and Rich-F is not shipped,
  so a switch would select nothing. It is kept on `exp/richer-prose` for Rich-F's next bench.
- **The arm's A3 note.** 0.4.6 already ships A3 (`planned.NOT_YET` / `_not_yet`, from
  fix/narration-inputs c4068bd2). The arm's copy would have doubled it.
- **A light line on every ordinary beat.** That needs an engine light reading for
  daylight, which is new work. The line reads `light_shown.sight`, so the moonlight lane's
  change to its `why` (no moon in "night under the open sky") flows straight through
  without a text conflict.

## Two fixes from the bench

1. **The leak list held ordinary words.** "landing" matched 3 base beats that showed no
   demonstration at all ("reach the landing" of the inn stairs). The list is now the
   demonstration's own words only (ferry-keeper, ferry, tarred), and a word the scene
   itself holds is never a leak.
2. **A8: why the arm's tells-check remakes rose (0.029 → 0.067 a beat, 3 → 7 in 105).**
   Read row by row from the bench records:
   - **2 of 7 were wait slots that wrote a day number** ("the early morning light of day
     five", "the dawn of the sixth day") beside a tell saying "the next day". The see
     block's hour line was the brief's WHEN, which opens with "day 4, …".
     - Fix: the hour line now drops the day number. The day belongs to the tell.
   - **3 of 7 were true catches with no tie to the block**: "ninety minutes" for 1 h 15
     (twice, once in a reply), and a sentence passed before the verdict allowed it.
   - **2 of 7 were doubtful flags**: "two Grippli guardsmen" (true), and "a true
     sellsword" (wording).
   - All 7 remakes passed, and none cut the slot. Nothing beyond the day-number fix is
     needed now. The real A8 audit (false cuts of colour sentences) stays open for when
     the fight arm adds more colour.

## Found live, not fixed here

On the owner's save (ruins hex, waiting an hour), the slot wrote "waiting until the sun
reaches its peak at midday". `gm/checks/land_described.py` read "peak" as mountain ground
and cut the sentence, and the page lost the hour's wait.
- This check predates this lane. It is a regex reading English, which the owner has ruled
  against.
- Richer hour prose raises its exposure.
- It is reported for its own lane rather than patched here.

Also seen live: in a wild hex, the brief's THE PLACE, IN ITS OWN WORDS carries the home
town's paragraph (Branford's priest-scribes). The see block puts that line nearer the ask.
It was not written on the page in the live turns, but the brief should say whose words they
are, or drop them, outside the settlement.
