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

## Built: the open list (2026-09-27)

The user's words: "finish the still open list first". Five items came out of the
residency report.

**1. A woman named Soren.** The world gives names no gender, and it gives none to its
characters either: 256 characters, every one written "them", with one `given` list per
people. "Soren" reads as a man's name only to an English reader. Guessing gender from
the shape of a made-up name would put English over the world's own language, the same
trap as the races ruling. This is recorded in `docs/from-world-bible.md` ("Known gaps")
as a request of the next export: a gender, or none, on each given name.

**2. "I go to the market and look for the bread seller" was read as looking for
"market".** The subject of a second seeking verb is carried by "and" or "then", and a
place kind is not a person (`judgement._a_place_word`).

**3. The planner added a stranger.** The older door, `inject_company`, read "I **ask**
around for the woman…" as addressing a woman, and spawned a body called "woman" beside
the finder's answer. It now steps aside for asking around, for anybody the finder
knows, and for a kind of person `introduce` will bring in within a settlement.

**4. Shop hours.** Research (sources in the session record):

- **Open is where the keeper stands.** Stardew Valley opens a shop only while its owner
  is in the counter's tile area, and Skyrim's vendor faction asks an hour window and a
  place.
- **A shut shop is not a shut building.** Pierre's Wednesday closure cut players off
  from the people inside, and complaints ran until the game added three overrides.
- **The keeper says when to come back.** CircleMUD's keeper speaks "Come back later!",
  "Sorry, we have closed, but come back later." or "Sorry, come back tomorrow."
- **Somebody is always open:** Skyrim's innkeepers.
- **Period hours:** the market bell at first light, most counters shut by mid-afternoon
  or evening, smiths and taverners working to the curfew bell (the 1345 Spurriers'
  ordinance forbade work after it).

Built in `rules/keepers.py`:

- **Hours by what the place is:**
  - taverns and inns always;
  - smithies, workshops, tannery, brewery, stables and the carters' yard until 21:00;
  - the market and everything else 06:00 to 18:00.
- **One door, `keepers.shut_here`,** asked by the trade panel, `buy`, `sell` and the
  brief ("COUNTER SHUT (fact)").
- **A stall's keeper goes home** when it shuts and comes back when it opens. A keeper
  under a roof lives there and can be talked to.
- **On the clock, not only on arrival** (the owner, 2026-10-09). Until then the going and
  coming happened only when the party ARRIVED somewhere (`Engine.settle_people`), so a
  player who waited the night out at a shut stall found it still shut and empty in
  daylight — the leather final pass's "the general store stayed shut next morning with
  her standing at it". The clock's one door (`Scene.advance`) now calls
  `Engine.settle_on_clock` whenever a stretch crosses one of residency's three-hour
  slots: keepers open and shut their counters with the party standing there, anybody
  out of the party's sight goes where their day puts them, and who came or went is told
  ("The keeper of the general store comes to the market and opens the counter.").
  Somebody standing with the party who keeps no counter stays (the doorway ruling); a
  slot crossed mid-fight is settled when the fight is over. Stardew's schedule entries
  begin "at the time", whoever is watching; Exult's off-screen teleport is the move.

Two defects the shop hours exposed, both fixed:

- **Every game began at clock 0, which the app reads as midnight,** under an opening
  that said "Mid-morning, in the market row". The clock now starts at the hour the
  opening names.
- **The brief never told the narrator the time.** Harmless while nothing read the hour;
  it now says "WHEN (fact): day 1, morning (about 10 in the morning)".

**5. Calling on somebody at home.** Research:

- **Where somebody lives is knowledge.** PF1e's gather information is Diplomacy: at
  least 1d4 hours canvassing, DC 10 for what is commonly known. The Alexandrian's
  targeted investigation says the same.
- **A visit is a knock with two gates,** the hour and the relationship. Stardew's houses
  keep door times, and a bedroom needs two hearts. U7's innkeeper "must be awoken".
- **Skyrim warns, then fines, a trespasser.** This door only knocks.

Built:

- **The `call_on` op,** detected in code from the player's words: "I go to the bread
  seller's house", "I go to her house", "I knock at her door", "I call on the old
  fisherman", "I ask around where the baker lives" (which only asks). "Her" or "him"
  means whoever the character spoke with last in this town.
- **Knowing the way is a `knows.home.<id>` tag on the character.** The person tells you
  if they are friendly. Otherwise you ask around, taking 10 on Diplomacy against DC 10
  for 1d4 hours of the world's clock. A character who cannot manage that is told who
  might say.
- **The house is founded once, owned by them, off a street:** "the house of the woman
  selling bread", or "Maren's house" once her name is known. From then on their day's
  "home" is that house (`residency.resolve` reads what they hold).
- **The knock:**
  - out: "Nobody answers", and a neighbour says where they are;
  - home by day or evening: the door opens to anybody indifferent or better;
  - between midnight and six: they are woken, which costs 3 regard, and only a friend
    opens.

  The party walks in, or stands in the street. `travel` straight to their house knocks
  first.

Not built: forced entry, knocking at a house the world wrote (keepers and world
characters keep no home yet), and a door that stays open to a friend once earned
(Stardew's "permanently unlocked").

**Live, the `calling` script (2026-09-27, three runs).** Run 3, 10 of 11 turns clean:
"I ask around where the bread seller lives" became "2 hours of asking around finds out
where they live. They live at Bram's house, off the warrens." Asked after midnight, "I
go to her house" became "Bram is woken by the knocking and shouts through the door to
come back in daylight. It does not open." She was indifferent to the character, so the
door stayed shut, and the party stood in the street.

Runs 1 and 2 found five defects, each fixed with a test in
`tests/test_calling_on_people.py`:

1. **"The bread seller" missed "somebody selling bread".** "Seller" was read as a
   stallholder's word. Generic trade words now mean selling, and the goods beat them in
   the roll.
2. **A `travel` to "the baker's row" rode beside the `call_on`.** The call now decides
   the walk.
3. **"Sleep until morning" was a fixed eight hours,** from five in the afternoon to one
   in the morning under a "morning sun". A night begun in the evening now runs to the
   next dawn.
4. **"Wait until ten at night" was planned as 140 minutes.** The engine's clock now does
   the arithmetic.
5. **"Her" went to somebody met in the same minute.** It now means the person whose home
   was last asked after.

**Still open, and flagged as its own task:** buying in narration never becomes a `buy`.
"I try to buy a coil of rope" was `narrate_only` in all three runs, and the narrator
sold rope at one in the morning with no coin moving. There is a `sell` injector and no
`buy` one. Shop hours are enforced on the trade panel and on any `buy` or `sell` that
reaches the engine.

## Built: buying, and the still-not-built list (2026-09-27)

The user's words: "Close the buying gap and have prompts like 'I try to buy a coil of
rope.' should open the trade tab [potentially with Rope in the basket.]. Then build the
still not built section".

**Buying.** Before this, a purchase in words was `narrate_only` in every live run, and
had it reached the engine there was nothing to buy: every shelf was drawn from the
crafting benches' materials (alum, bismuth, quicklime). Research:

- **Talk hands off to a trade screen and never settles a sale:** Fallout's
  `ShowBarterMenu`, Neverwinter Nights' `OpenStore`, Baldur's Gate 3's Trade button.
- **The thing named is matched against real stock,** and refused rather than guessed
  when it is not there (tbaMUD: "Sorry, I haven't got exactly that item.").

Built:

- **Counters stock goods as staples,** never sold out, from the Core Rulebook's Goods
  and Services (the same `GEAR` list the outfitting screen sells from, plus Table 6-9's
  food and drink):
  - the market: the outfitting list plus bread, cheese and meat;
  - a tavern: food and drink only;
  - a smithy: its ironmongery.
- **Your earlier ruling holds:** "a single store should not have every possible item",
  so the other 70-odd rows of the table are not on every counter.
- **`judgement.purchase_sought` reads "buy / try to buy / want to buy X"** and skips
  buying a man a drink, time or a room.
- **The turn returns `trade: {open, want}`,** and the page opens the panel.
  `/api/trade` matches the want against the shelf (`goods.match_want`: every word, the
  plainer item winning, "a loaf" is bread). It picks the row, or the keeper says they
  have none.
- **The prose is told the screen opens and settles nothing,** and a `buy` the model
  wrote for it is dropped.
- **Nothing opens at a shut counter,** with nobody keeping one, or for a customer the
  keeper will not serve.

Verified in the running app, on a scratch data folder: "I try to buy a coil of rope."
opened the panel with "hemp rope (50 ft)" picked at 1 gp, and paying left 11 gp and 50
ft of rope.

**Homes for keepers and the world's people.** Pierre lives in his shop and Belethor
sleeps upstairs in his, so a keeper under a roof lives on the premises. A stall's keeper
has a house of their own, founded on the first call, and goes there when the stall
shuts. A character the world wrote is found by name in their own town and given a body
as a `spawn` would. Their house is founded on the first call, and they keep the plainest
day: home by night, by day where they were first found. A trade shop under a roof is
knocked at in the small hours. A guardhouse or a guildhall is not; the first cut
refused the guardhouse at midnight and the storeys suite caught it.

**A door that stays open to a friend.** Stardew Valley's bedroom, once opened at two
hearts, "is permanently unlocked even if the heart meter goes below 2 hearts". So a
character let in as a friend holds `bond.welcome.<key>`, and the door opens at any hour
from then on. The exception is somebody who has come to hate them, which Stardew's
hearts cannot express.

**Breaking in.** PF1e Core Rulebook numbers:

- **The door:** a good wooden door, locked, breaks at Strength DC 18. Table 13-2 and the
  Breaking Items table disagree for most doors and agree for this one.
- **The lock:** an average lock is Disable Device DC 25, +10 without thieves' tools,
  trained only, and the player rolls.
- **Noise:** Perception's own DCs judge it. The sound of battle is -10 and a whisper 15,
  so a door forced is heard at 0 and a lock picked at 15, +10 for a sleeping
  householder. One who hears it loses 20 regard.
- **Witnesses:** anybody in the street sees it. Seen, the character is suspected; seen
  again, wanted. That is Skyrim's warning before the fine, in this app's own law tags.
- **A forced door stays broken.**

**Live, the `homes` script (2026-09-27, three runs, gemma-4-12B).**

- **The knock:** at three in the morning the bread seller "is woken by the knocking and
  shouts through the door to come back in daylight". At six she was already at work:
  "Nobody answers … A neighbour says: The one selling bread is at the north crossing at
  this hour."
- **Breaking in:** a lock pick failed and a kick broke a door in. Seen by two
  bystanders, the character was suspected; unseen, not.
- **Two defects found and fixed:**
  1. **The model wrote extra ops beside the break-in,** a `give` of "lock on her door"
     and a thug spawned as "new" who then "witnessed" the break-in. A break-in turn now
     keeps nothing beside the door.
  2. **The prose opened a door the dice held,** in two runs out of three. The review
     check caught it every time, and the model's rewrite never fixed it. The backstop now
     cuts the beat from the first sentence that opens the door and ends it shut. Live, it
     left "The lock does not give, and the door stays shut. What do you do?", thin
     because the false opening was the beat's first sentence, but true.
- **Not changed:** "I go to the market and buy a coil of rope" planned no walk twice,
  and the party stayed where it was. Room-to-room travel is deliberately the model's to
  name (`inject_travel`'s documented refusal to guess a place), so this is the model's
  miss and was left.

## Built: people you can see are in the scene (2026-10-01)

The owner's ruling overturns the one of 2026-09-27 ("the prose records people; engagement or
the plan makes them actors"): "show described people in the scene. if i can see them they
should be in the scene as a fully made person ready to be interacted with and saved if not
already existing."

**Measured on the owner's save (Sam, 2026-10-01):**

1. Gorm told the player a human woman lives in "the house three streets over". She was
   recorded twice in one beat (p16 from the narration's report, p17 heard from Gorm), and
   both at the Velvet Veil, where the talk happened.
2. "I enter the house of the human woman Grom spoke of": the plan's `call_on "human woman"`
   was refused "There is more than one — which human woman do you mean?", and the finder
   logged `population-miss` seven times for the words human, woman, grom, speak.
3. The beat then showed "a figure … It is a woman" at the top of the stairs. She was never
   an actor: the next turn's condition on 'woman' was refused (unknown ref), and every "her"
   after it went to Quin Nutmeg, the only woman the engine held, in another room.

**Prior art.** The Inform 7 Handbook's scenery rule: "if an object is mentioned in the room
description, it should probably be implemented" — a player who reads somebody in the room
will try to address them. The same tradition keeps the opposite case apart: Eric Eve's
Epistemology gives *seen* and *familiar* (known of, not found) as two flags (Inform Recipe
Book §5.5), and somebody spoken of is familiar. Inform's Recipe Book §7.16 models a social
group as individuals with collated descriptions; this repo already keeps a crowd as
scenery or a troop, so a crowd stays that. For the name slip, Damerau (1964): about 80% of
misspellings are one insertion, deletion, substitution or transposition; "Grom" for "Gorm"
is one transposition. Ian Bicking's Intra notes (2025) were read for an LLM-narrator
precedent: it lets "ungrounded" narration add colour without touching formal state, and
offers no rule for people; nothing found describes an LLM game that embodies the people its
narrator describes, so this is not claimed as precedent.

**What was built:**

- **Seen or heard, read from the sentence** (`judgement.seen_in_beat`). Seen needs positive
  evidence that is THEIRS: a being-here or looked-at verb (`_PLACES_THEM_HERE`,
  `_SEEN_HERE`) in the person's own clause ("a figure IS SILHOUETTED"), or the person after
  the eye ("you see a man …", "at the top of the stairs, a figure"), in a sentence that is
  no report of somebody's words. Heard: only in speech; every sentence about them hearsay
  ("he told you a woman lives there", "if a guard sees you"); or only ever the object of a
  search or a question ("the search for the woman"). A body is what a misread turns into a
  phantom, which is why seen is the strict side. The first cut read any cue anywhere in the
  sentence, plus `action_sentences`; the first live replay walked on a phantom woman from
  "You are still standing before him, and the search for the woman …" and "a woman who
  exists in the stories of the desperate", with a Ratfolk face appended to the beat.
- **`record_people(beat=...)`**: a seen person is recorded where the party stands and
  marked `shown`; a heard one is recorded with no place (`spot=""`), heard from the one
  person in conversation, and a resident when the beat says they live somewhere. Somebody
  heard of in the last beat or two whom the words describe is the same record
  (`population.heard_of_match`). A vague head with a stated sex becomes it: "a figure …
  It is a woman" is recorded as "woman".
- **The bodies** (`judgement.embody_seen`, run by `play/aftermath/seen_people.py` in the
  "people" stage after `speaker_real`): through the one door (`population.embody`), wearing
  the rolled face and life, on a square, saved. Never a duplicate: a record with a body is
  that body; somebody held elsewhere in town under every word the prose used walks in; in
  somebody's own house with them in it, a vague figure there is the householder (unless
  the figure "enters"). Read off `scene.founded`, never the turn's outcomes — law 3's
  ratchet (`test_three_laws`) caught the first cut reading `effects`. At most three new
  bodies a beat; plurals and counted groups make none; in a fight none. A heard-of person
  whose body stands in the party's room is marked seen.
- **The grant** (`rules/granted.py`): a question that places the person elsewhere ("who
  lives there?") records a heard-of grant with no place, which binds nobody minted in the
  room; and it merges with the record the same beat's narration made.
- **The finder** (`population.find`): a hearsay clause ("Gorm spoke of", "the barkeep told
  me about", "that Gorm mentioned") is read off the phrase; among those who fit the rest,
  the one heard of from that speaker is chosen, across every ring. A proper name one slip
  from exactly one name the campaign holds is that name. A miss is logged once per phrase.
- **The yes** (`granted.affirms`) also reads the asked-for words given back first: "'A
  woman, aye,' he rasps" was Gorm's live answer, and nothing recorded her.
- **The call** takes the player's words when the plan wrote the introduce placeholder
  (`call_on who="new2"`, live), reads "the house of X" as a call on X, and keeps the
  player's clause (`judgement._call_on_keeps_who_told`), and a body
  made only to be walked to its own door is not marked seen in the party's room
  (`population.embody(seen_here=False)`); that had put the woman's day at the gate.
- **Unseen and unplaced is at home** (`residency.resolve`), not at the settlement's first
  place.

**Live replays (2026-10-01, gemma-4-12B, in-process `/api/say` on a scratch copy of the
owner's save, the defect's p16-p18 removed and the party put back in the Velvet Veil).**
Ten runs; each of the first eight found something the unit tests had not, and each is now
a test in `tests/test_seen_people.py`:

1. The cue was not the person's (the phantom woman above).
2. Gorm's "A woman, aye," is a yes the opening-yes reader missed, so nothing recorded her.
3. An answer about her that never says yes ("a woman alone in a house like that") recorded
   nobody. About somebody who lives elsewhere, an answer that speaks of her (by the noun or
   her pronoun, not opening with a no) now records her heard of; a grant HERE still needs
   the yes, because it binds the next body made.
4. The plan wrote `call_on who="new2"`.
5. The woman made to be called on was made in the tavern and stayed there: her own door
   went unanswered with "The human woman is at the Velvet Veil".
6. "The question you posed, concerning the woman three streets over" recorded her on the
   outskirts.
7. "there is no sign of the woman" booked her, and the next beat's "You find the woman
   standing in the entryway" made nobody, because `note_cast` reads the definite as
   somebody already booked (`_shown_again` now reads the ledger too).
8. "the human woman Grom spoke of" missed her because the roll gave the unseen woman the
   town's Ratfolk face. A face nobody saw is not in the finder's bag, and a people the
   record never stated rules nobody out, as a gender already did.

Run 9, the owner's sequence end to end: "it is a human woman who lives in the house 3
streets over, right?" → one record, p16 'human woman', no place, heard from c8, resident,
granted Human. "I go to the house of the human woman Grom spoke of." → `call_on` resolved:
"4 hours of asking around finds out where they live. The human woman opens the door and
lets you in." The party stood in the house with c11 'human woman', she/her, Human, one
record. Run 10: "/cheat the woman is overcome with lust and pounces on me" planned
`condition helpful` on c11 and resolved; in the save it had been refused as "unknown ref
'woman'".

Not settled by this work: the planner's own slips on these runs ("I go back to the Velvet
Veil" planned `travel` with no place; "I walk back to Gorm at the bar" founded "the bar"
and walked out of the tavern), and the narrator writing a house the engine had not moved
the party to. The fallback when a hearsay clause names a speaker who told of nobody that
fits is still the ordinary search, so it can ask "which do you mean" between people the
speaker never mentioned.
