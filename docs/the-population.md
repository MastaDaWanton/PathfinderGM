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

## Built (2026-09-25)

**Step 1 — the record, the roll, glimpses.** `rules/lives.py` rolls a life in coherence
order; `rules/population.py` keeps the records in `Scene.population`, saved with the
campaign; `views._finish` notes every person the beat introduced before promotion, and a
promoted actor wears the face their record rolled. Measured:

- 3,000 rolls, 0 fallbacks; the top goal is 7.9% of people.
- Replay corpus (real model prose): 30 people noted, 0 rolls fell back.
- The quirk chart was widened from 45 frames to 170. With 45, the 46th person met in a
  town repeated somebody's habit, and 21 of the 45 (47%) were one sentence, "… whenever
  {occasion}". Now a town of 150 repeats no habit, "whenever" appears in 13.5% of frames,
  and no opening verb starts more than 10% of them. Distinct quirk texts over 3,000
  people fell from 848 to 685, because most new frames have no slots. Per-town
  uniqueness is what a player sees, and that went from 45 to 150.

**Step 2 — finding someone.** `population.find` searches the scope rings, using a
synonym table (`content/people/synonyms.json`) plus the occupations' own match words.
Two rules shape a fit:

- A gender the record never stated does not rule someone out; a different stated gender
  does.
- A vague word ("the woman") searches only the room, the people seen in the last hour,
  and the people met.

The finder is wired into `scope.look_for`, and through it into `absent_answer` and
`answer_the_absent`, and into `repair_unknown_refs`. That last one now binds the GM's
invented ref to the person the population already holds, through `judgement.embody`,
the one door `promote_cast` also uses, instead of spawning a stranger in her place.

The old code, measured with the woman recorded at the party's own spot: all three
lookups answered "No woman in the doorway is here, and Vormoor has none the world
names."

A search that misses and scans every ring takes 66 ms over 5,000 records, so no index
has been built yet. Misses reach the turn log as `population-miss`.

**Live checks (2026-09-25, gemma-4-12B, the real HTTP loop).** Three runs. Each found
something the unit tests had not:

1. The opening's own company ("the woman at the bread stall") had no record and no face,
   because only `views._finish` noted people. A plural ("neighboring merchants") was
   rolled one life as if it were one person. Fixed: `begin` records its company, and
   `judgement.record_people` is the one rule the turn and the replay corpus share,
   keeping crowds out. The corpus went from 30 people noted to 27; the three dropped
   were "guards", two "Nirkor porter" and four "laborer".
2. A planted glimpse ("old woman mending fishing nets by the doorway") was spoken to. The
   planner wrote `narrate_only`, so the finder was never asked. The prose wrote "the old
   woman", and the booking door made a second person with a second face. Fixed:
   `population.here_as`. The booking asks the finder first, and only reaches people the
   visit's ledger does not already hold, so the ledger's definiteness test is never
   overruled. Rerun: the prose's "woman" became her, wearing her rolled face, across
   both turns.
3. The same run showed an older duplicate: the prose's "old man" was booked beside the
   opening's "the old man ahead of you", because the opening company was never on the
   ledger. Fixed by booking it there with its ref.

Still unexercised live: the repair path's binding (the planner has not yet reached for an
invented ref to a glimpse), and "which do you mean". Both are covered by unit tests only.
The booking door also clips phrases ("man in a stained leather", "woman with a sharp");
that door is replaced in step 3, so it is recorded here and left alone.

## Decided (2026-09-25, later): a world roster across playthroughs

The user's words: "they need to exist here separately from the ones in an individual
campaign because the campaign ones have history with a PC that doesn't exist".

- **Who goes into the world's shared roster:** residents and travellers when they are
  created, and anyone the player engages with, whatever they started as. "If I decide
  I want to interact with a passing homeless nomadic man then when he is created he goes
  into the shared roster as a person that can be used again."
- **Found again on purpose:** "what if i like that person and want to find them in
  another playthrough." That is a feature, not a side effect: the player can go looking
  for a roster person from another playthrough.
- Built on a global id per person. The campaign record points at the roster person and
  keeps only what happened in that playthrough.
- "Another playthrough" means a new character rolled in the same world, not a character
  moving between worlds. The roster belongs to the world; each character's save keeps
  only that character's history with its people.
- **What carries over:** the life as first rolled. Nothing from another character's game.
- **Reuse, in the user's words:** "When B's scene needs 'a baker in the market', it could
  use the town's roster baker first making sure to use people in the destinations that
  make sense for them but also dont always do that or the campaigns will feel to
  similar. in the case of shops or stalls or social/political office the person who owned
  that place or title before is perfect but if the game wants an NPC that isnt tied to a
  location or title it should not always grab already created people. if it just needs a
  shady merchant or a fisherman at the docks it should make new people at first and as
  that kind needs rolled again bring up the old character." So there are two rules:
  - **Tied to a place or a title** (the keeper of a shop or stall, a social or political
    office): the roster's holder of that place or title is used.
  - **Untied** (a shady merchant, a fisherman at the docks): new people first. As more of
    that kind are needed in this character's game, roster people of that kind start to
    come back.
  - Either way, only in places that make sense for them: a resident near home, a
    traveller on their roads.
- Not built yet. Research first: RimWorld's world pawns (generation reusing existing
  pawns) and Dwarf Fortress's historical figures are the prior art to read.
- **No keep mark and no kept-people list.** The user's reasoning: "no character starts
  knowing very many people and unless a person gives their name or has their name given
  the character shouldn't know it. And if the PC metagames they should be able to find
  the people by name and description." So a roster person is found the ordinary way, by
  asking around by description or by name. This needs two changes: a name rolled when the
  person is created (today `true_name` is rolled only when they get a body), so it is the
  same in every character's game; and the finder matching that name. Townsfolk know
  Maren's name even when the character does not, so asking after her by name is fair in
  the fiction too.

## Decided (2026-09-25): hidden facts may direct, never tell

After "I look for a scribe" in a tavern found the man in the corner, whom the population
had rolled as a scribe though the prose never said so, the user's words: "it would be fine
if the prose had you ask if anyone was a scribe and the man walked up and asked but
ultimately you are correct that the information should be hidden from the player. also
its still fine as long as the player isnt told the man is a scribe and is just directed
to him."

So a rolled life (work, wants, goal, hobby, quirk) may decide who the finder points the
player at, and the fiction may reveal it through play: he steps up when asked. No line
the finder writes, and nothing the brief states, names the hidden fact.
`tests/test_finding_someone.py::test_a_hidden_fact_may_find_them_but_is_never_said`
holds the finder's side. A world character's authored role, such as Bregan Duskwatch
the temple scribe, is public canon and is not a hidden fact.

## Built: manner in the brief (2026-09-25)

§7, which the build order had left without a slot. Before it, every rolled life was
stored and nothing read it. Each person with a record now carries, in WHO IS HERE, on
every turn:

- **their two loudest traits, as behaviour**: the `shows` lines ("watches hands before
  faces and asks why before how"), never the trait words;
- **their quirk**, on first meeting and then only after `QUIRK_EVERY` (5) turns, held as
  engine state;
- **"IS A CHILD (fact)"** for a minor, because the table's adults-only rule depends on
  the narrator knowing.

Wants, goal, hobby and work never reach the brief.

The research that set the shape:

- **Two traits, as behaviour.** Salient attributes crowd out the rest (The Chameleon's
  Limit, arXiv 2604.24698, preprint). Generic framing breeds caricature (CoMPosT, EMNLP
  2023). Dwarf Fortress reports only facets outside its neutral band.
- **The quirk cadence is engine state.** Valve's Response System keeps `respeakdelay`
  as state, and a small model cannot count "now and then".
- **Secrets stay out of the brief entirely.** A secret a 12B model is told leaks
  thematically about 83% of the time, and "don't reveal" helped only frontier models
  (Holtzman & West, arXiv 2605.10794, preprint).

**Live, the town script, 12 turns, 13 people with records:**

- No want, goal or hobby leaked (literal check).
- Manner shows: a stallholder rolled to "watch the way people speak" was written as
  "doesn't look at your hands or your weapon, but focuses on the way you speak".
- Quirks are played in paraphrase, and the word detector missed every one. So the quirk
  now rests from the beat it was offered in, not from a detected showing; otherwise it
  would have been offered every turn.
- The one "trait named outright" was "open" (a gate). Common words are not read as
  labels.

## Built: residency and movement (2026-09-27)

Step 4, first half. The user's words were "go ahead with residency and movement";
"since last we met" is the second half and is not built yet.

**What was wrong, measured before building:**

- **The road out of town destroyed everybody left behind** (`Scene.depart` in the
  journey). A woman met at the gate, Soren Kragnirath at regard 70, came back two days
  later as Korvin Korvath at regard 35. Her record kept her face and life, but her
  name and standing lived on the body the road threw away.
- **Nobody in a town ever moved.** A stallholder seen at noon stood at her stall all
  night.
- **Travellers never travelled.** Merchants, carters and minstrels stayed put, although
  the occupation table already marked them mobile.
- **Nothing wrote `last_met`,** so the finder's `met` ring was always empty.

**What the research found** (two passes and a critic, 2026-09-27; URLs in the session
record):

- **Ultima VII keeps eight three-hour slots per person.** Off screen, Exult does not
  walk anybody to their slot; it teleports them there (`teleport_offscreen_to_schedule`
  in actors.cc, read directly). It disabled walking in from off screen because it
  "causes NPCs to teleport to on-screen far too often (e.g., Blue Boar bartenders)".
- **Shadows of Doubt abandoned precomputed daily routines** (DevBlog 15), because
  spontaneous reactions broke them. Stardew Valley overrides its schedule keys by date,
  weather and marriage.
- **Placing a traveller by arithmetic from a departure time has no confirmed game
  precedent.** The Oblivion claim that low-process actors are teleported by elapsed
  travel time is a blogger's inference, and the critic found no primary source for it.
  Kerbal Space Program's "on rails" orbits are the nearest precedent. Its failure mode,
  an unloaded object that cannot feel its environment, is why nothing here resolves
  "what the road did to them" yet: the catch-up step will, seeded, when they are next
  met.
- **Players lose scheduled NPCs:** Majora's Mask needed its notebook, and Stardew has
  wiki schedules and a map-locations mod. PF1e already has the answer in Diplomacy's
  gather information: at least 1d4 hours canvassing, DC 10 for what is commonly known.
  The finder says where somebody is.
- **Nobody dies of being away.** Skyrim's `Protected` flag means only the player may
  kill that actor, and players resent off-screen deaths (Bannerlord). The catch-up step
  must honour this.

**What was built:**

- **`rules/residency.py`: where somebody is, as a function of their record and the
  clock.** Asked only when needed, and never on a tick.
  - **Residents keep a class routine over eight slots.** Home, work, gather, temple and
    market resolve against the places the settlement actually has. Work is where they
    were first seen. Trades with their own hours override their class (the innkeeper,
    the lamplighter), and a guard keeps a day or night watch, rolled once. The slot they
    were first seen in is theirs at that place, because an observation beats the key.
  - **Travellers walk the world's real roads from where and when they were last seen.**
    Each stay lasts a seeded number of days, and traders prefer the trade roads. The
    walk is stored on the record ("store what was rolled") and re-anchored whenever they
    are seen again. Only `random.random()` is drawn, the one method Python promises
    stable across versions.
  - **Transients (pilgrims) take one road out once the party leaves them,** spend a day
    where it leads, and are then gone.
- **Where nobody can walk in is an `offstage` place id** under the town: at home,
  lodging, on a road, gone. `travel` only reaches places `places()` lists, so no door
  leads there. Somebody at home is found by asking.
- **`population.where_now`** answers the finder in three steps, the first that holds:
  1. their body's place;
  2. where the party saw them, if the party has not left that place since (the
     ruling: "should stay there until i leave or something moves them");
  3. the key or the road.
  The HERE and settlement rings read it.
- **`Engine.settle_people`** runs once per arrival (`Scene.moves`), after the batch:
  everyone with a record goes where the answer puts them. Some people stay put:
  - whoever came along with the party;
  - whoever was seen here since arriving;
  - anybody down, held, travelling with the party, in conversation or in a fight;
  - residents of other towns, reckoned when the party is there.
  - anybody without a record (a keeper at the counter, a world character, a spawned
    thug).

  A reload where the party already stands is not an arrival. A resident settled has
  eaten and slept, so their hunger counters reset (NetHack's catch-up shape).
- **A journey keeps anybody the world has a reason to keep:** a record, a world
  character, or a standing with the player. These are RimWorld's keep reasons. A
  spawned creature with none of these still goes, and so do the dead.
- **`join_talk` writes `last_met`** and makes a glimpse an acquaintance.
- **The finder's line says where they are, never what they are:**
  - "is at the market at this hour"
  - "would be indoors, at home. By day they are at the market"
  - "left Vormoor for Dustgate 2 days ago, and is on the road"
  - "is in Ledgerwarren now"
  - "has moved on"

**Measured on the way:**

- **An hour's `advance` over 300 bodies took 0.515 s.** `tick_effects` computed
  `hp_max` for every body, and that asks the race registry, whose homebrew freshness
  check reads the folder from disk on every call (about 1 ms per `has_state`,
  pre-existing, flagged as its own task). With no timed effect, nothing can end: now
  0.007 s.
- **Settling 300 bodies went from 1.3 s to 0.03 s** once the cheap questions went
  first.
- **Walking 2,500 travellers' roads 30 days on went from 25 s to 1.0 s** once roads
  were cached per world. After that the walk is stored, and a miss over 5,000 records
  takes 0.3 s.
- **In Aurvantis every road is a trade road** (64 of 64 settlements), so the trader's
  preference only matters for a world with other roads. The test proves the weighting
  on a subset.

**Not built yet:**

- visiting somebody at home (the planner's `found` needs the owner in the room);
- shop hours for keepers;
- "since last we met";
- the world roster.

**Live, the `return` script (2026-09-27, gemma-4-12B, the real HTTP loop).** Two runs,
each 12 turns and 11 of 12 clean.

- **The finder's answer reaches the plan and the prose.** The morning search got
  `not_here`: "The one selling bread in the market is at the north crossing at this
  hour". The narrator wrote it as a notice pinned to her empty stall. Asked after dark,
  the answer was "would be indoors, at home. By day they are at the north crossing".
- **Her body went where her day put it:** home at 18:00, back at her work place at 11:00
  the next day. A stranger the roller made a merchant was on the road to Xylorvotha by
  the end.

Defects the runs found, each fixed with a test in `tests/test_residency.py`:

1. **The roller and the finder disagreed about trades.** "Somebody selling bread" was
   rolled a gravedigger, and "the foreman with the tally board" a merchant, who then
   left town. `lives.occupation_for` now falls back to the finder's stemmer, and the
   goods name the trade (bread → baker, foreman → labourer).
2. **"I ask her name." came back as `introduce who="her name"`,** and the prose check made
   the narrator write her in. A possessive naming no person is refused
   (`population.names_a_person`).
3. **`introduce` then `travel` then `say` made her at the place being left,** and the
   question went to the one other person in the market. Now `introduce` of somebody
   already here moves after the plan's walk, and `say` with a named listener who is not
   here falls back to nobody.
4. **The answer read "At this hour The somebody selling bread…".** It now reads "the one
   selling bread", capitalised as a sentence.
5. **"I ask around for the woman who sold me bread" was read as "woman".** The capture
   stopped at "who", and "sold" never stemmed to "sell". A definite description now
   keeps its "who" clause, and the finder falls back to the head when nobody answers to
   the clause. An indefinite one ("a guide who knows the grass") introduces a guide, and
   the clause is no part of who they are. The stemmer knows the irregular past.

Not yet seen live: the round trip between towns. Both runs were stopped on the road
before they reached the next town, so name and standing surviving a journey rests on
the unit test.

Noticed and left: "I go to the market and look for the bread seller" is read as looking
for "market", because the first verb phrase wins. The plan answered correctly anyway.
