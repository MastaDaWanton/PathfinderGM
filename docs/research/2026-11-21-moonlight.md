# Research: the moon on the page (lane fix/moonlight, 2026-11-21)

Playtest 2026-11-20 item #22: one move ended in "a moonless night", the next beat said "the
dim, moonlit gloom". The narrator made up the moon twice, once present and once absent.

## What the engine holds today (read before searching)

- `Scene.ambient_light` (rules/engine.py) gives open sky at night as **dim**. Its docstring
  says "the book's moonlit or starlit night. The app keeps no moon and no cloud". The engine
  never chose a moon, so neither page sentence is the engine's.
- `gm/checks/light_shown.sight` is the one derivation `prompts.light_now` reads, and the
  richer-prose branch's "what is here to see" block reads it too (exp/richer-prose
  `planned.see_lines`). For that same dim night it gave the reason **"night under the open
  sky, starlight and moonlight only"**. So in a fight or a search at night, the engine's own
  brief told the narrator there was a moon, and the engine holds no moon. That is half of
  #22, from our own code.
- The other half (a beat with no light line saying "moonless") is the narrator filling an
  unstated fact.
- `rules/tracking.py` takes its Survival DC from the same dim/dark reading ("dim" is the
  book's moonlit night, +3). Nothing anywhere stores a moon phase or a cloud cover.
- The world owns its sky. Aurvantis (fixtures) has "twin moons (Aurel and Vantis)" with
  "opposed cycles", as free text in its premise. The owner's world (fantasia) has no moon
  data, only culture: new-moon rites and full-moon dances. Neither export gives a moon as
  data (count, cycle, phase).

## PF1e

CRB, Vision and Light (https://aonprd.com/Rules.aspx?Name=Vision%20and%20Light&Category=Additional%20Rules,
read 2026-11-21):
- **Dim light:** "outside at night with a moon in the sky, bright starlight".
- **Darkness:** "outside on a cloudy, moonless night".

So the moon is mechanics, not colour. Moonless *and* cloudy is darkness (50% miss chance,
effectively blinded), against dim (20%). A narrator who says "moonless, overcast" has
described a light level the engine does not apply. A narrator who says "moonlit" has
described one the engine only happens to agree with. Either way the model has authored a
mechanical state, which law 3 forbids.

## How other traditions model the sky

- **tbaMUD/CircleMUD** (`src/weather.c`, https://raw.githubusercontent.com/tbamud/tbamud/master/src/weather.c,
  read 2026-11-21). The engine holds `sunlight` (SUN_RISE/LIGHT/SET/DARK) and `sky`
  (CLOUDLESS/CLOUDY/RAINING/LIGHTNING) as state, and sends the sky messages only to outdoor
  rooms (`send_to_outdoor`). **It has no moon at all**, and its sky text is only ever the
  engine's own messages. The writer never makes up a sky.
- **Morrowind / OpenMW** (`apps/openmw/mwworld/weather.cpp`,
  https://raw.githubusercontent.com/OpenMW/openmw/master/apps/openmw/mwworld/weather.cpp,
  read 2026-11-21). Each moon is **world data**: `Moons_Masser_*` / `Moons_Secunda_*`
  fallback settings for speed, daily increment and fade. The phase is computed from the game
  day: `(phaseDay / sDaysPerPhase) % sPhasesPerCycle`. The cycle belongs to the game's data,
  not the engine. UESP gives a 24-day cycle for Morrowind and Oblivion, where the phase
  length is a climate setting. That figure is from talk pages and the Oblivion CS wiki
  (https://en.uesp.net/wiki/Lore_talk:Moons); I could not fetch UESP's CLMT format page
  (HTTP 403).
- **Cataclysm: DDA** (`src/calendar.cpp`, `tests/moon_test.cpp`,
  https://sources.debian.org/src/cataclysm-dda/0.H-1/tests/moon_test.cpp). There are eight
  phases from a day count against `turn_zero` and a lunar-month length. Each phase has a
  constant light value that feeds the night light level, and the phase changes at noon "so
  the light doesn't shift in the middle of the night". The sun and moon positions are not
  modelled. This is the closest precedent for moon phase changing a light level. I read it
  from the search summary of those files, not from the code line by line.
- **NetHack** (`phase_of_the_moon()`, hacklib.c; https://nethackwiki.com/wiki/Luck). The
  phase comes from the real calendar, with mechanical effects: +1 Luck at full moon,
  cockatrices at new moon. The phase is engine state with effects, never text.

Across the traditions, a sky that appears in text is held as state. The two that model a
moon hold its cycle as the **world's data** (OpenMW's per-moon settings) or as a fixed
calendar of one Earth-like moon (CDDA, NetHack). The one with no moon data (tbaMUD) simply
never says a moon. None of them lets the text writer decide the moon.

## Grounded narration and unstated facts

- The Labyrinth AI GM paper (arXiv 2409.06949, 2024; authors not checked) and the structured-knowledge-tree
  detective game (arXiv 2609.23043): consistency improves when the game state is held
  symbolically and the model is given it, rather than left to track it. That paper counts
  violations of the held state as hallucinations (17.8% for LLM-only, 6.27% with the tree,
  from its abstract).
- Negation does not hold as an instruction. In Jang, Ye & Seo, "Can Large Language Models
  Truly Understand Prompts? A Case Study with Negated Prompts" (arXiv 2209.12711, 2022),
  performance on negated prompts *falls* as models scale. This matches our own record
  (CLAUDE.md: every fix that relied on instructing the model failed). A brief line "say
  nothing of the moon" is the weakest option, and it puts the word "moon" in front of the
  model besides.

## Decision

**Both, in the house shape: the engine stops claiming a moon it does not hold; the beat's
read-back catches any moon the page claims and a targeted rewrite takes it out; and World
Bible is asked for moons as data, so the real phase can be fed later.**

1. `light_shown.sight`: the night reason is now "night under the open sky". The engine
   stops feeding a moon it does not have. This flows unchanged into `light_now` and the
   richer-prose see block, which both read `sight`.
2. `beat_verify`: the read-back's `time_of_day` already covers "the light, the sky, the
   hour". Its instruction now names the moon explicitly. Any hour claim whose quote carries
   a moon word is a contradiction ("the engine keeps no moon in this sky"). It is repaired
   by the existing one-sentence rewrite with that fact named, and backstopped by its cut
   (`beat-hour`). This is the same shape as the underground sky check
   (`_underground_only` + `_SKY_WORD`, playtest 2026-11-16 #62): a model reads which
   sentence says the hour and quotes it; code checks the quote against a closed vocabulary.
   No regex picks the sentence or decides what it means. Exempt, as every hour claim is: an
   appointment the engine set this turn (`_hour_told`).
3. docs/for-world-bible.md **ask #34**: moons as data (name, cycle in days, phase on day 1),
   so the engine can compute the phase the OpenMW way. A moonless night can then be told,
   and once cloud is also held, it can become the book's darkness.

### Rejected

- **A default moon (one Earth moon on a 29.5-day cycle).** CDDA and NetHack do this, but
  their world is Earth. The owner ruled for the enchanting phases "This is not earth"
  (rules/sky.py, 2026-10-05), and Aurvantis has two moons. A default moon would be the
  engine contradicting the world. Fixes are world-agnostic.
- **Reading the world's free-text cosmology with a model to find its moons.** That is a
  model authoring a world fact the engine would then treat as data (cycle lengths, how many
  moons). It belongs in the export, and ask #34 asks for it.
- **A standing sky line in every night brief** ("the sky: stars; no moon"). A line that is
  always there becomes a formula (`hour_now`'s measured reasoning). A negated fact is the
  instruction shape that fails (Jang et al.), and it names the moon to the model.
- **Cloud cover now.** The engine keeps no standing weather (only a journey's weather
  *event*, which belongs to another lane). It stays unheld. Clouds are not policed here:
  "clouds" is already in `_SKY_WORD` for the underground check, and an overcast sky does not
  contradict the engine's dim on its own. The PF1e darkness case needs moonless *and*
  cloudy.
- **Accepting the narrator's first moon claim as fact and holding later beats to it.** That
  lets a model author a mechanical state (the light level), against law 3.

### Second pass

I re-read each source against the claims above. Corrections made:
- CDDA's phase-to-light detail is from search summaries of the source files. It is marked
  as such and not presented as read code.
- The UESP 24-day cycle is talk-page and CS-wiki material, and is marked as such.
- The "17.8% vs 6.27%" figure is from the paper's abstract as surfaced by search. I did not
  read the full paper.
