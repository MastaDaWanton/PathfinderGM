# The population

*Design, 2026-09-25. Phase 2 of the deferred list, merged with the narration redesign
(`docs/declared-not-guessed.md`): the planner's `introduce` op is how people enter the
population, so the two are one piece of work. Built only after the user has read this.*

---

## What the user asked for, in their words

- Everyone the prose describes is recorded; "I dont care if a database grows of random
  people as long as we can search the data base quickly and precisely".
- Each person is tied to a location: the woman "should stay there until i leave or
  something moves them"; afterwards she "remains a resident of the city/town/village
  unless she is a merchant or traveller" — "those people should persist move around and
  their lives should evolve".
- Notes carry "things they want and goals for the future hobbies and what they do for work".
- "A date of last interaction can be established and then compared at the next time they
  are interacted with and then they can be updated with what has happened in their life".
- "Roll a personality from a massive chart and everyone should get a quirky thing to make
  them special also rolled", and results incoherent with earlier rolls are locked out.

## What the research found (2026-09-25; four passes, citations in the session record)

- **Detail where the player is, abstraction elsewhere, catch-up on return** is the pattern
  every system that kept a large population converged on: RimWorld keeps off-map pawns
  "mothballed" and garbage-collects the unimportant; Dwarf Fortress makes anyone named you
  meet a historical figure so they "don't suddenly disappear", but abandoned "every citizen
  a figure" for a quadratic slowdown; Shadows of Doubt abandoned precomputed daily routines
  for simulation that is detailed only near the player; NetHack catches a returning monster
  up for the time it was away. The Alexandrian's recurring-NPC log is literally "since last
  we met".
- **Tried and abandoned:** Oblivion's Radiant AI (NPCs pursuing goals broke quests — "the AI
  is so goddamned smart and determined it screws up our quests"); Skyrim's Radiant Story
  over-firing; The Sims 3 changing families while away, uncontrollably; Caves of Qud's full
  history simulation (they generate events and rationalise causes instead); Generative
  Agents' model-decided days (drift to odd places, "thousands of dollars" for 25 agents).
- **Finding a person needs scope, not semantic search.** On a 2,000-person synthetic set,
  word match + a synonym table picked the right person 70% of the time inside the scene
  and 4.6% across everyone — globally 97% of references fit more than one person (91 on
  average), which no retriever can fix. BM25 commits to wrong answers more often than
  plain matching; embeddings would need a second model download, always return a nearest
  neighbour even when nobody fits, and at best could close a 15-point gap on unknown words
  (unmeasured). Inform and TADS resolve by scope first, then ask "which do you mean".
- **Personality at scale stays coherent by structure:** Dwarf Fortress's facets are numbers
  with a silent middle band; RimWorld and Crusader Kings keep 1-3 traits with declared
  opposites and conflicts; The Sims 4 shipped one-way conflicts (order-dependent) — the bug
  to test against. Players notice the characterful part, not the combination (Compton's
  "10,000 bowls of oatmeal"); ten people drawing from 40 quirk frames share one ~71% of the
  time unless the draw is without replacement. A small model voicing many traits caricatures
  them (CoMPosT, EMNLP 2023); instruction-following falls with instruction count (ManyIFEval).
- **Licensing:** the repository is public. Paizo's personality prose is not Open Game
  Content; Worlds Without Number's tables are not openly licensed. The IPIP item pool is
  public domain (structure for the axes); the Dungeon World SRD is CC-BY 3.0. Everything
  shipped is our own writing on that structure.

## The design

### 1. A person record, light, in the save

Not a character sheet (1.4 KB bare, several KB with gear, measured): a record beside
`Scene.people`, promoted to a full `Actor` only when the person enters play (spoken to,
targeted, in a fight). Fields:

- identity: `id`, `phrase` (the words she was introduced with, verbatim — what the player
  will paraphrase), `people_id`, `appearance` (names + faces, as today), `name` (the world
  pool's, given in play or not), `home` (settlement), `spot` (place id), `mobility`
  (resident / mobile / transient, from the occupation);
- life: `work`, `wants`, `goal`, `hobby`, `personality` (axis scores), `quirk`;
- memory: `first_met`, `last_met` (campaign clock), `life` (dated events), `tier`
  (glimpse / acquaintance / figure), `regard` (the existing 0-100 effect, once an actor).

### 2. How people enter

Declared, never scraped: the planner's `introduce{role, description, how}` op
(`declared-not-guessed.md`) creates the record in the same model call that plans the turn
— a woman in a doorway costs no extra call. The prose paints freely; a person it describes
who was not declared is noted as a **glimpse** (phrase, spot, clock) with no body, so she
is still findable later (the user's question: "there is nothing left of her?" — there is).

### 3. The roll, in order, each locking out what contradicts the last

People and body → work → personality → wants → goal → hobby → quirk. Every chart row
carries tags and declares what it cannot sit beside; a row that conflicts with anything
already rolled is not in the pool for the next roll. Exclusions are stored both ways and a
test walks every pair (the Sims 4 bug). A pool emptied by exclusions falls back to a
neutral row and logs it. Seeded by the person's id; what was rolled is stored, so a reload
never re-rolls anyone.

- **Work** from the settlement's own data where the export has it (trade sells/buys,
  places' staffing, the people's Livelihood and Craft), else an occupation table.
- **Personality:** about ten bipolar axes (IPIP structure, our own words), each rolled on a
  bell curve so most people sit in a silent middle; the two most extreme become the words
  the model is given (three when a third is very extreme). About 1,600 distinct voiced
  personalities before any quirk.
- **Quirk:** composed — frame × object × occasion ("counts the coins in her apron whenever
  somebody lies to her"), about 40 × 60 × 30 slots, thousands of legal combinations after
  tag checks. Objects come from her work and the world's own goods, so every word is
  grounded. Frames declare the body they need (checked against her face, as `faces.py`
  already does for hair) and the temperaments they forbid. **The frame is drawn without
  replacement within a settlement**, so no two people in a town share one until the bag
  empties. A quirk is flavour: it never drives an engine action (Radiant AI).
- **Wants, goal, hobby:** tables keyed by occupation class; goals a Pathfinder-flavoured
  list in the shape of Dwarf Fortress's life goals.

### 4. Where people are

While the party is in a place, everyone there stays until the plan moves them or the party
leaves. Afterwards: residents stay residents of their settlement, found by a schedule key
(Ultima VII's eight 3-hour slots: home, work, market, tavern, temple) rather than by
simulation; mobile kinds (merchant, caravan guard, pilgrim, sailor, minstrel) follow the
world's real routes by arithmetic from a departure day, so a merchant met in one town can
be found days down the road; transients leave when the scene closes.

### 5. Since last we met

Nothing ticks per turn and nothing iterates the population (Dwarf Fortress's trap). When the
player engages somebody, the clock is compared with `last_met`; the gap buys rolls on a
life-event table (about one per week away, capped per meeting — decided lively), each
checked against the world's real people and places. Every event is an engine record with
provenance — tag, day, the people and places it names, the roll — and anything that moves
a number (an injury, a debt) is an `ActiveEffect`. The model writes one sentence of it;
the narrator is told the facts ("Since you left: Maren married Tobin the cooper"), never a
score. Phase 7's world tick adds what should happen even if the player never returns.

### 6. Finding someone

Scope rings, first clean answer wins: in the scene → named in recent turns → met →
this settlement → everyone. Within a ring, a person fits only if every content word of the
player's phrase matches her phrase, face, work or name after a synonym table; one fit is
her, several is "which do you mean — the woman at the well or the one mending nets?",
none moves out a ring. Ranking among fits by facts (in the scene, recent, in conversation),
never by word statistics. SQLite FTS5 (already in the frozen build) indexes the record for
speed; misses are logged so the synonym table grows from real play. Embeddings only if a
real-play measurement shows they add precision.

### 7. What the player sees, what the model sees

Player: the quirk as behaviour in the prose; traits as they show in play. Model: two or
three trait words, the quirk, one line of how it shows — and the quirk reaches the brief on
first meeting and then only now and then, with a detector that drops it if it was just used
(caricature, measured risk). Engine only: the axis numbers.

## Cost

Introducing: no extra call (the plan call). Becoming an acquaintance: one call (7-25 s) to
voice the rolled tags, validated against them. Catch-up: none — dice and tables; the
sentence of news is a template or one short call. Search: milliseconds.

## Build order

1. The record, the roll (with the exclusion tests), glimpses from prose — no behaviour
   change to what the player sees yet; measured on the replay corpus (how many glimpses per
   draft, how many rolls hit a fallback).
2. Finding someone (scope rings, synonyms, "which do you mean"), wired into the lookups the
   player's words already go through.
3. `introduce` in the planner, and the booking door closed (`declared-not-guessed.md`).
4. Residency and movement; then "since last we met".

## Decided (2026-09-25)

- **Visibility: learned in play.** A person's wants, goals, hobbies and personality are
  hidden until they show: the quirk as behaviour in the prose, the rest entered in the
  player's notes on that person once learned by talking, asking around or watching.
- **The quirk pool holds habits and fascinations only.** Disabilities, illnesses, tics,
  phobias and addictions are kept out; bodies keep their own marks (`faces.py`).
- **Catch-up is lively: about one life event per week away**, capped per meeting.
- **Crowd:** a combination of "while you're there" and "until something moves them"
  (options 1 and 3 of the session's question): everyone the prose describes is recorded
  and located; residents persist in their settlement, mobile kinds travel.
