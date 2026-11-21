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

## Found live, then fixed on this branch (coordinator, 2026-11-21)

### 1. The land check cut "the sun reaches its peak"

On the owner's save (a ruins hex, waiting an hour), the slot wrote "waiting until the sun
reaches its peak at midday". `gm/checks/land_described.py` matched "peak" in the biome
table, read it as mountain ground, and its backstop cut the sentence. The page lost the
hour's wait.

**Two shapes were weighed:**
- **Move it to the read-back.** `beat_verify` already works this way for the hour, the
  setting and the underground sky: a model quotes the claim and fills an enum slot, then
  code checks the quote against the engine's closed list (`_setting_wrong`, `_SKY_WORD` on
  `c.quote`). A "ground" slot would be a new field in a call whose fields compete.
  docs/beat-verify.md measured recall falling when slots were added, and CLAUDE.md warns
  that a model asked for N things answers in parallel. It would need its own bench.
- **Narrow the word list (chosen, as the smaller correct change).** Every biome-table word
  with an everyday sense is out of the judged set, so the cut only fires on a word that can
  mean nothing but land cover. Words removed: peak, summit, cliff, plateau, alpine,
  volcanic, frost, frozen, icy, snow, polar, arctic, northern climate, arid, oasis, tropic,
  moor, tree, grove, glade, copse, thicket. Still judged: the land nouns themselves (forest,
  swamp, desert, tundra, glacier, hills, mountain, volcano, crag …) and the trees by name,
  which is Bobby's measured case.

**This is still a word list over English, held to precision.** The reader shape is the
real fix, for a later lane.

**Other checks with the same shape (a word list deciding what English says), named but
not rebuilt:**
- `gm/checks/empty_roll.py` (`_GROUND`, `_FIRE`)
- `absent_person.py`
- `body_shown.py`
- `direction.py`
- `face_kept.py`
- `hook_leaks.py`
- `light_shown.py`

**Live recheck.** "I wait an hour among the broken walls" now reads: "You wait among the
broken walls as the time passes, the sun climbing until it is midday. You sit amidst the
rubble and stone, watching the hour pass in the quiet of the ruins." No cut.

One earlier recheck lost the wait another way:
- the tells check flagged "as the sun climbs higher" at 1 pm, and that flag is arguably
  right;
- the remake came back unfinished, so the slot was cut.

That is the A8 exposure: a colour clause inside the act sentence takes the act with it
when it is cut. It is left open for the A8 audit.

### 2. The home town's words in a wild hex

`prompts.scene_brief` printed THE PLACE, IN ITS OWN WORDS from `location`. A hex, and the
site in it, is filed under its nearest town, so the hex got the town's paragraph ("Branford
runs on priest-scribes …"). `gm/brief/place_facts.py` did the same with the town's looks
keys ("Architecture: coral and driftwood stilts" in the ruins).

**The fix.** `places.off_its_streets(location, at)` tests one thing: is the party on ground
the settlement files under itself, but outside its streets (fields, a road, a hex, a site)?
- Both brief sections read that one test.
- The town's own words are dropped there. Nothing World Bible exports describes a hex.
- The looks keys are dropped there: Urban Life, Architecture, Daily Life.
- The social and law keys stay: Governance and Tension still hold out there.
- A wild site the world wrote is its own location, so it keeps its own words.
- The see block reads the brief, so it is fixed by the same change.

**Live recheck.** At the ruins' gate, "I look around" read: "You scan the immediate
surroundings, taking in the stark architecture of the gatehouse and the weathered stone of
the wall-walk above". The see block held only the site's own UNDERFOOT ("the gatehouse
either side, and the wall-walk over it"), the ground and the hour. No town words were in
the brief.
