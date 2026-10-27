# Known matters, invented jobs, and tracking toward nothing

Branch `fix/known-matters`, 2026-10-27. This doc covers the owner's report on 0.2.21 with
Planned narration, what was built, and the job model the engine still lacks. The job model
is a design with questions for the owner, and none of it is built yet.

## 1. The report, and what the save shows

The owner wrote:

> While tracking the caravan I am supposed to be guarding the narration kept saying i was
> looking for tanna ashborne's coldwood which is not a request that i ever took or heard
> for that matter. Finally i have been tracking the caravan but I am seemingly not moving
> toward the caravan after the 1st track.

The save and turn log (read only; nothing from them is copied here) show five things.

1. **The Coldwood quest came from a scheme.** "The lost thing" opened "Find Tanna
   Ashbourne's lost Coldwood" at the market on day two. The quest card was a *quest* from
   that hour onward:
   - it appeared as `QUEST:` in every brief;
   - it was in the Journal;
   - it counted as the player's own matter in the pull's salience (`own = kind == "quest"`).

   Nobody had put it to the player.
2. **The pull fired with nobody there to carry it.**
   - Row 90 used the `overheard` approach at the market. The budget dropped that slot.
   - Row 137 used `go_between` in the fields, where nobody was present to be a go-between.

   The planned slot read "A matter the engine keeps open: Find Tanna Ashbourne's lost
   Coldwood — Search the approach for the Coldwood." From that, the narrator wrote "You keep
   the goal of finding Tanna Ashbourne's lost Coldwood in mind". The owner pressed That's
   wrong on it.
3. **The engine never held the caravan job.**
   - The "hiring table" opening says "Hands wanted for the week, fed and paid at the end of
     it", and the opening opens no scheme and no quest.
   - Over five planned replies the clerk invented the details: an escort of supplies to an
     outpost, bandits, paperwork tomorrow, signing, and a caravan that "moved toward the
     outskirts".
   - `scene.agreements` was empty. There was no caravan actor, no place for one and no card
     for it.
4. **Row 136: "I follow the tracks in search of the caravan."** The reader read this as
   `follow`, which owed no op. The plan walked the party a quarter hour to "the fields" and
   made a bare Survival check.
5. **Row 146: "I continue to track the caravan."** This made a `track` with no params. It
   found whoever the party had seen on that ground, and moved nobody.

## 2. Prior art (searched before designing; a critic pass flagged the weak claims)

**Knowing about a matter is not the same as taking it on.**

- **Inform 7, Eric Eve's *Epistemology*.** Every thing is *seen* or *familiar*, and *known*
  means either one
  ([RB 5.5](https://ganelson.github.io/inform-website/book/RB_5_5.html)). It models
  knowledge only, not commitment. `docs/design-d-people.md` already cites it.
- **Baldur's Gate 3 journal guidelines.**
  - Journal content must be "Known", meaning delivered clearly through dialogue, a book or
    the environment.
  - Acceptance, documents, the personal call and the unexpected may start a quest.
  - Entering a region, picking up an object, combat and **a voice bark** (the overheard
    case) should not.
  - Source: [Journal Design Guidelines](https://docs.baldursgate3.game/index.php?title=Journal_Design_Guidelines).
- **Skyrim.** Overheard rumours were pushed into the journal as Miscellaneous objectives.
  Players removed this with mods, for example *The Choice is Yours*
  ([nexus 26359](https://www.nexusmods.com/skyrim/mods/26359)), which also makes quests wait
  for the player to agree. That description comes from a search snippet; I could not open
  the page. Starfield kept auto-adding under the label "Activities". So **Bethesda did not
  abandon this; its players did.**
- **Ironsworn.** A quest is the character's only once they *swear* it, and leaving it is a
  move of its own ([Starforged SRD, quest moves](https://rsek.github.io/starforged-srd/moves/quest)).
  I could not source a formal "heard of but not sworn" state.
- **The Angry GM.** "You never … make choices for them or assume choices on their behalf"
  ([Ask Angry: morale and agency](https://theangrygm.com/ask-angry-morale-and-agency/)).
  He attributes this to Dungeon Magazine's guidelines; I did not see those guidelines.

**A job is bound to real things before anyone speaks of it.**

- **Daggerfall quest scripts** declare their `Person`, `Place`, `Item`, `Foe` and `Clock`
  before the offer text (QuestorOffer / RefuseQuest / AcceptQuest). A remote place resolves
  to a real site in the province
  ([questing source docs](https://www.dfworkshop.net/static_files/questing-source-docs.html)).
- **Battle Brothers.** Contracts have an employer, negotiated pay and an explicit accept.
  The escort caravan is a real party on the map. The developers **abandoned** contracts
  that "artificially spawn things for you to fight" in favour of contracts that arise from
  real settlement situations, and they also abandoned money-only haggling
  ([dev blog 95](https://battlebrothersgame.com/dev-blog-95-contract-changes/)).
- **Mount & Blade.** The escort caravan spawns as a map party with a destination town. This
  comes from a wiki snippet I could not open. Bannerlord's caravans re-routing and
  outrunning the player show what a real counterpart costs to run.
- **RimWorld.** Quests carry an accept-by and a complete-by timer, and their pawns and
  sites are created with the quest ([wiki](https://rimworldwiki.com/wiki/Quests)).
- **Traveller patron encounters** separate what the characters are told from what the
  referee knows. A referee table, not the patron's words, settles what is really going on.

**Tracking.**

- **CircleMUD/tbaMUD `do_track`** looks the target up world-wide first. If nothing answers,
  it says "No one is around by that name" with **no roll**. On success it runs a
  breadth-first search toward the target's *current* room
  ([graph.c](https://raw.githubusercontent.com/tbamud/tbamud/master/src/graph.c)). This is a
  compass to a live target, not a trail that ages.
- **Pathfinder 1e Survival** requires a check per mile, with the DC set by the ground plus
  1 per day and per hour of rain ([d20pfsrd](https://www.d20pfsrd.com/skills/survival/)).
  A trail is a record of something that really passed.

## 3. What was built

### 3.1 Item 1: a matter the player never heard is never their goal

**The record.** `Card.known` is one of `unheard`, `heard`, `offered` or `taken`. The field
is written only when it is set, so a card saved before it round-trips byte-identically.

- A quest from a scheme that *starts* a story (`schemes._starts_fresh`: a favour, a debt,
  a lost thing) opens `unheard` (`rules/schemes.py`, `_open_one_card`). A scheme that
  *continues* the player's own story opens `taken`, as it always did. Those are the schemes
  that open on `has(pc, knows.…)`: a name to clear, a price on their head.
- The `quest` op and a loss to get back open `taken`. That is `open_quest`'s default.
- The write-back is `cards.note_heard`, run after the beat (`play/views.py`, beside
  `note_mentions`). It sets `heard` when the pull reached the player in passing (`overheard`
  or `go_between`) and `offered` when the matter was put to them (`asked`, `greets` or
  `sends_word`). It only acts when the beat actually carried the card, and it never moves a
  card back.
- The player takes a quest on through the `quest` op, naming its exact title or id
  (`Engine._take_up`). A quest they never heard of is refused, and the refusal says why.
- The take-up does not wait for the planner. Live, the planner proposed nothing for "I
  will find your Coldwood for you". So the act-to-op table (`acts_to_ops.take_ups`) handles
  it:
  - it sees the player speaking to the giver of a quest they know of;
  - it asks the reader one closed question (`interpret.confirm_take_up`);
  - on a yes it builds the `quest` op with the card's own title and objectives.

  Measured live: the tell was "Borin Achereth takes it on: Find Brix Sootspar's lost
  Coldwood, for Brix Sootspar", and the card became `taken`.
- A scheme step that ticks an objective of a quest the player has not taken still fires.
  Its outcome now carries `not_own`, so the planned slot and the free beat are read back
  for it (`schemes._progress_not_taken`).
  - Live, this was the second leak path: "the approach, the ground where Glowvine grows"
    came back as "searching the soil where the luminescent Glowvine is known to take
    root". The owner's save shows the same at row 82.
  - Holding such steps back until the quest is taken was tried first. It broke 18 scheme
    tests whose stories move without a take-up, so it is a question for the owner (§4.2,
    question 7).
- An old save's quest without `known` is read from what the card carries. A scheme's quest
  is `offered` if any approach put it to the player, `heard` if one reached them in passing,
  and `unheard` otherwise. Any other quest is `taken`. The owner's Coldwood card therefore
  reads as `heard`, never as the player's own.

**One reader.** `cards.standing(card)` returns `own`, `offered`, `heard`, `unheard` or
`situation`. Every consumer goes through it:

- **The pull's salience.** A quest counts as `own` only once taken, and "open objective"
  presses only on an own quest.
- **The brief** (`cards.brief`).
  - The prose never sees an unheard quest.
  - The plan sees it marked "NOT YET PUT TO THE PLAYER … nobody's goal of theirs".
  - Offered and heard quests are labelled as such, and their objectives are listed as "what
    they want done".
- **The Journal** (`cards.quest_log`) shows own and offered quests only. Overheard rumours
  stay out, following BG3 and Skyrim's players. Each row carries `standing`.
- **The GM answers** (`play/gm_answers.py`) follow the same rule.

**A carrier, or no pull** (`cards._pull_one`). A matter that is not the player's reaches
them only through somebody. If nobody can carry it, the next matter in line is tried, and if
none can be carried there is no pull.

| Approach | Who carries it |
|---|---|
| `overheard`, `greets`, `asked` | its own person, standing here |
| `go_between` | a person of this place standing here (not a companion) |
| `sends_word` | a runner, and only inside a settlement |

The first `go_between` design required "somebody the player is talking with", but
`hooks.scene_state` makes that state BUSY, so such a carrier could never exist. This lane's
first test measured that.

**The wording.**

- The free narrator's head for somebody else's matter says whose it is and "NOT the
  player's", and it carries no objective.
- The planned slot (`planned.matter_slot`) is built from the pull's facts and approach. It
  says "the giver is here … seen or overheard at their own trouble", or names the carrier
  who mentions it. When the player turned to the giver, the giver's ask folds into that
  giver's reply slot.

**The read-back.** `beat_verify.own_goal_sentence` asks the model for the number of the
narration sentence (speech blanked) that presents the matter as the player's own goal. The
answer is held to an enum of sentence numbers.

- **Planned slot:** it is asked again with the sentence named. If it still says it, the
  slot is dropped (`planned._not_their_goal`).
- **Free beat:** the sentence is cut in code (`GMAgent._not_their_goal`).

**The urgency review** (`drops-the-thread`) now fires only for the player's own quests.

### 3.2 Item 2: tracking honesty, and no work made up on the spot

**A track names its quarry.**

- `track` takes `quarry` (the player's words) and `follow`, written by the act-to-op table.
- A `follow` that names nobody standing here and no known place owes a `track` with
  `follow` (`acts_to_ops._follows_a_trail`). The plan's own walk for it is replaced.
- Which phrase names the trail's maker is a reading. The live reader put "the caravan" and
  "the tracks" in either slot, so `interpret.confirm_quarry` asks one closed question per
  phrase. A phrase that names somebody the engine holds (`tracking.quarry_of`, which uses
  the people finder) needs no question.

**The engine answers it** (`tracking.after`).

- A quarry nothing holds: "No trail of the caravan crosses this ground … there is no trail
  of the caravan to follow."
- A held quarry whose trail is not on this ground, or which the roll did not read, is said
  so.
- A trail that is followed walks the party to where its maker is now. The walk is a
  `travel` placed next in the queue, through the door a call-on's walk already uses.
- A trail that leads to another settlement is described as "a journey, not a walk" and is
  not walked.

**No made-up work** (planned replies). A reply slot whose speaker holds no live,
known-to-the-player quest is marked `no_job`. `beat_verify.invented_job_sentence` reads it
for a sentence that puts *particular* work to the player: a named task, who it is for,
where, when, papers or pay. Saying that hands are wanted, or quoting a price, does not
count. If such a sentence is found, the reply is asked again with that sentence named. If
it repeats, the sentence is cut, unless it is the whole reply, in which case it stays and
the turn log says so.

**A successful roll that found nothing is no longer "the attempt works".** Live, the beat
said "you find no tracks of the caravan", which was true. The read-back's attempts question
took the roll's success (21 against DC 15) to mean "the attempt works" and rewrote the beat
into "you find the tracks of the caravan". Now a successful `track` that found nothing, or
found nothing of its quarry, is not asked as an attempt; the tell is the record. A failed
roll is still asked, which is the gold beat `ho-att-tracks-found`.

**Not built (said, not hidden).**

- The free narrator's replies are not read for made-up work.
- A trail across country is followed in one walk and one check, not mile by mile.
- The job itself still does not exist in the engine. That is §4.

## 4. The job model: a design for the owner's ruling

The traditions agree on one point: a job binds real things **before** anyone speaks of it.
Daggerfall declares the questor, place, item and clock first. Battle Brothers' caravan is a
party on the map, and its developers removed contracts that spawned things to order. The
hiring table opening breaks this rule. It speaks of work, and nothing in the engine stands
behind the words.

### 4.1 The smallest structure that would hold

A **job** is a quest card of a new kind, `job`, reusing everything a card already has
(giver, objectives, reward, `known`, the Journal and the pull). It adds a closed record:

| field | what it is | where it comes from |
|---|---|---|
| `employer` | a person the engine holds (the clerk, the wagon master) | the opening's lead, or a keeper |
| `work` | one of a closed list: `labour`, `count`, `guard`, `escort`, `carry` | the opening document; for a hiring table, the player's own answer ("carry, count or fight") read as an enum |
| `counterpart` | for `escort` and `guard`: a **group actor** (the caravan) with a body, members and an `at` | minted by the job, like a scheme's slot, at a real place: the carters' yard, the gate |
| `meets` | a place id and a clock time | the opening's `when` ("the wagons leave at first light"), a real place |
| `route` | an origin and a destination settlement id | the world's roads (`rules/journey.py`) |
| `pay` | priced by the engine: `tradecraft.work_offer` for labour, a guard's day-rate per CRB hireling tables for escort | never a number from a model |
| `terms` | `on_completion`, `half_now`, `per_day` | a closed choice; Battle Brothers' lesson is to negotiate how the pay is made up, not the sum |

How the record moves:

- **Accepting.** The player agrees in their own words, and the existing `quest` op (or a
  `take_job` op) takes the job up. The `quest` op's take-up branch is now built and is what
  this would reuse.
- **Working.** For `labour` and `count` the job *is* the existing `work` op: a week's
  Profession or untrained labour, paid at the end. That covers the hiring table today with
  no new actor at all.
- **Escort and guard.** The caravan is a group at `meets` at the stated time. The
  `journey` op travels *with* it (it joins `came_along` for the road), and the job's
  objectives tick on arrival.
- **Prose checks.** Once the record exists, a reply can be held to it: "the outpost" either
  is the job's destination or is made up.

### 4.2 Questions for the owner

1. **Should the hiring-table opening's "fight" answer become a real escort, or a week of
   paid guard work in town?** The second is the `work` op the engine already has, with no
   caravan at all. The first needs the group actor and travelling with it, which is several
   lanes of work.
2. **Is a caravan one actor (a group, as Battle Brothers' party) or several people
   (drivers, guards, a master)?** "Seen people are real" suggests the people. Battle
   Brothers and Mount & Blade use one party.
3. **Should the clerk invent nothing until the job exists, or may the opening document
   carry a short list of real jobs?** For example, "the wagons for the outpost leave at
   first light", with the outpost bound to a real settlement and the wagons minted at the
   yard.
4. **What happens to a job not turned up for?** RimWorld has an accept-by timer, and
   Daggerfall's clock only starts when the job is accepted. Should missing the meeting time
   cost regard with the employer, as the scheme outcomes already can?
5. **Pay terms: is the sum fixed by the engine and the terms negotiable (Battle Brothers),
   or the sum negotiable by Diplomacy (the existing `request` path)?**
6. **The owner's current save has a "caravan" that never existed.** Should it be left for
   the read-back to answer honestly from now on, or cleaned up by hand?
7. **Should a stranger's errand advance before the player takes it?** Today a scheme's
   objective ticks when the player happens to stand where the work is done. The beat is
   now read back so it cannot call that the player's search, but the objective still
   ticks. Holding those steps until the quest is taken is the stricter reading of "never
   the player's goal unless taken". It changes 18 scheme tests' stories.

### 4.3 The owner's answers (2026-10-27)

1. "I can fight": the clerk offers EITHER a real escort (when one is going out) or a week of
   guard work (the existing `work` op).
2. A caravan is SEVERAL REAL PEOPLE: drivers and guards, each a person with a sheet.
3. Openings MAY list real jobs; the hiring table creates real work at the start.
4. Not turning up: the job lapses and the hiring table's regard drops a little.
5. Pay: the book's hireling wage for the work's danger; Diplomacy can raise it up to 3x,
   through the Make Request machinery. The engine computes every number.
6. The owner's existing save is left as it is.
7. Someone else's errand: the objective may tick or count silently, but NOTHING about it
   reaches the page for an unheard quest. Heard is different.

## 6. Real jobs, as built (branch `feat/real-jobs`)

### 6.1 More prior art (searched 2026-10-27; a critic pass corrected two claims)

- **The pay.** CRB Services: "Hireling, trained 3 sp per day", "Hireling, untrained 1 sp
  per day", "a minimum wage"; trained hirelings include "mercenary warriors ... teamsters"
  ([CRB equipment](https://legacy.aonprd.com/coreRulebook/equipment.html)). Ultimate
  Equipment lists no separate guard or caravan-guard wage
  ([UE services](https://legacy.aonprd.com/ultimateEquipment/gear/lodgingAndServices.html)).
  *Pathfinder Player Companion: Cohorts & Companions*, "Contingency Services", prices a
  hireling by the work's Risk — harmless 3 sp, questionable 6 sp, hazardous 1 gp, deadly
  3 gp, suicidal 3 pp a day — "multiplied by the level of each hireling squared"; Risk
  starts at 1, +1 for challenging terrain or hostile non-sentient inhabitants, +2 for harsh
  terrain or hostile sentient inhabitants above the hireling's level
  ([d20pfsrd hirelings](https://www.d20pfsrd.com/equipment/goods-and-services/hirelings-servants-services/);
  the page number could not be confirmed). The first research pass called this rule
  third-party; the critic pass found it is Paizo's.
- **Haggling.** Battle Brothers **abandoned** haggling the sum: the old way was "ask for
  more money until the employer denies" and was "automatic, there's little thought behind
  it"; contracts now negotiate how the pay is made up
  ([dev blog 95](https://battlebrothersgame.com/dev-blog-95-contract-changes/)). Its hidden
  "annoyance" per haggle is known only from a player's decompile, not from the developers.
  The owner chose the sum by Diplomacy; the book's "+5 per additional request" and "a
  refused request does not change" (CRB p.93) stand in for the employer's patience, and the
  3x ceiling bounds it.
- **Missing the hour.** Daggerfall's escort employer, arrived at late, "leaves in a huff
  without paying" ([UESP](https://en.uesp.net/wiki/Daggerfall:The_Escort)); its reputation
  runs -100..100 and a failed quest costs 2
  ([UESP](https://en.uesp.net/wiki/Daggerfall:Reputation)). RimWorld keeps an accept-by and
  a complete-by timer ([wiki](https://rimworldwiki.com/wiki/Quests)). Mount & Blade's
  briefing names days and the real limit is indefinite
  ([wiki](https://mountandblade.fandom.com/wiki/Escort_Merchant_Caravan_to_(town))).
- **One party or several people.** Battle Brothers' and Mount & Blade's caravans are one
  map party; Daggerfall's escort is one person; RimWorld's guests are individual pawns. The
  owner chose people (answer 2), which "seen people are real" already asked for.

### 6.2 The record

A job is a card of kind `job` (`rules/cards.py`, tag `situation.quest.job`, so every prefix
question asked of a quest is asked of a job), with its own record in `Card.job`
(`rules/jobs.py`):

| field | what it holds |
|---|---|
| `work` | one of `labour`, `carry`, `count`, `guard`, `escort` (`jobs.WORK`) |
| `employer` | the clerk's ref |
| `meets` | the road head toward the destination (a real ring place), its name, and the minute: noon today while the morning is young (to 10:00), else first light tomorrow |
| `route` | origin and destination settlement ids (`journey.legs_from`, land roads only), the hours on foot |
| `counterpart` | the caravan's label, its people's refs, the master's ref, and when it `left` |
| `pay` | `base_per_day_cp`, `per_day_cp`, `days`, `risk`, `times`, `level` |
| `terms` | `on_completion` (the opening's own "paid at the end of it") |
| `state` | `open`, `met`, `paid`, `lapsed`, `gone`, `declined` |

`standing`, the Journal (`cards.quest_log` reads `cards.tasks`), the brief ("JOB, TAKEN
ON"), the pull's "open" press, `take_up`, `note_heard` and `objective_done` treat a job as
the task it is; `quests()` stays the quests alone, so the quest take-up never takes a job.

### 6.3 What happens, and where each answer lives

- **Answer 3, real jobs at the start.** The hiring table's document lists `jobs`
  (`content/openings/core.json`): an escort with four caravan rows (master, two teamsters,
  a hired sword) and the week's work (`carry`, `count`, `guard`). `openings.stage` opens
  them (`jobs.open_from_opening`), validated by `openings.validate`. Both open `heard`:
  the clerk's call reached the player, and no particular job is put to them until the
  clerk answers what they can do or what the work is (then `offered`, in the Journal, and
  what "I'll take it" agrees to). Opened `offered` at first, a bare "I'll take it" signed
  the player on to a caravan the clerk had not yet mentioned.
- **Answer 2, people.** Each caravan row is minted by `jobs._mint`: a codex block for the
  role (`npcs.choose`), a true name and a face from the world's pools, a people
  (`person_words.settle_people`), standing at the road head through the arrival door. No
  population record, so residency does not walk them off; `Engine._stays_in_the_world`
  keeps anybody a live job holds.
- **Answer 1, the offer.** The reader is asked one closed question when the player's
  words reach an employer here (`interpret.confirm_job`: what the words do, which of
  carry/count/fight, which job put to them). `acts_to_ops.jobs_spoken` builds the `job`
  op whole; the plan never writes one (`intents.CODE_ONLY_OPS`, dropped in `apply`, out of
  the plan's op enum). `Engine._op_job` offers the escort for "fight" while it is going out
  (`jobs.escort_going_out`), with the week's guard work beside it; once the wagons have
  gone, the guard week alone. Carry and count are the week's work.
- **Answer 5, the pay.** `jobs.per_day_cp`: carry 1 sp and count 3 sp flat (CRB); guard
  and escort by Cohorts & Companions' Risk times level squared. A road is questionable
  (+1 for the beasts `ontheway` really rolls for), hazardous over forest, hills, marsh,
  jungle or desert, deadly over mountain or frozen ground. The haggle is the Make Request
  check made of the employer of the job just offered (`Engine._make_request` routes a
  payment request to `Engine._haggle_job`): the book's DC, the player's own roll in the
  popup, +5 per earlier request today, a refusal that stands; a granted one multiplies the
  offer by Influence Attitude's steps at half the offer each (`jobs.haggled_times`: 1.5x,
  2x per 5 over, never past 3x).
- **Accepting.** The job is the player's (`known` taken). For the escort, the agreed sum
  goes into the caravan master's purse — the guild's money for its guard, the only coin
  the job puts into the world — and the tell says where and when to be. For the week, the
  `work` op runs at the job's wage (`work` takes a code-only `job` param), seven days
  through the clock and the body, and the card is done and paid.
- **Meeting, travelling, arriving.** `jobs.settle`, once per batch beside `defeat.settle`:
  the player at the road head by the hour is counted in (`met`). A journey to the
  destination takes the met caravan's people along (`jobs.coming_along`, added to the
  journey's escorts, so they reach the far end and `came_along`); the road's own encounter
  roll is the only trouble on the way (Battle Brothers abandoned contracts that spawn
  things to fight). Arrived with them, the master pays out of his purse
  (`Engine._mark_payment`), and the card resolves.
- **Answer 4, not turning up.** Past the hour plus `GRACE_MINUTES` (60), with the player
  not standing with the wagons, the caravan leaves: its people go to the far town's road
  back, and the road head keeps when they went. A job taken is `lapsed`, let go, and the
  clerk's regard drops `MISSED_REGARD` (5, what a Diplomacy failure by five costs); the
  tell says so. An offer never taken is `gone` and costs nothing.
- **Tracking.** `tracking.quarry_of` answers "the caravan" with the job's group
  (`jobs.group_named`: every word of the phrase is a word of the group's own label, the way
  the counter matches a want); at the road head its trail ends where the master stands;
  gone, the wagons' trail (Large) leads off toward another settlement, "a journey, not a
  walk".
- **What the clerk may say.** The planned reply slot of an employer carries the job's facts
  (`jobs.slot_facts`: the road, the hour, the people, the days and the pay) and is marked
  `holds`; `beat_verify.invented_job_sentence(held=...)` reads it for work that is NOT that
  work, and `planned._no_job_made_up` asks again with the sentence named, then cuts it.
- **Answer 7, silence.** A scheme step whose progress is on a quest the player has never
  heard of (`schemes._unheard_progress`) is silent: the objective ticks, no outcome is
  returned, so there is no tell, no planned slot and no line linking the place or the thing
  to the errand, and its XP line is not banked to ride a later tell. A heard quest keeps its
  tell, marked `not_own` for the read-back.
- **Answer 6.** Nothing migrates a save. Jobs open only when a start is staged; an old card
  round-trips without a `job` key.

### 6.4 Not built (said, not hidden)

- The caravan's own journey when the player is not with it is not walked: its people are
  put at the far town's road back when its hour passes.
- Once the player has reported at the road head, the wagons wait for them to set out:
  nothing starts the journey but the player's own word, and standing with the caravan past
  its hour does not lapse the job.
- Pay in advance and per-head terms are not offered; the terms are the opening's.
- The caravan's people fight beside the player only if the fight's own sides put them
  there; a road ambush does not enrol them.
- A job finished pays its wage and no story XP.
- The free narrator's replies are still not read for made-up work (Planned is the default).
- Only the hiring table lists jobs; other openings and the world's own export do not yet
  (World Bible has no job export; see §6.5).

### 6.5 What World Bible would need to export

Nothing is required: a job is built from what every export already has (settlements,
`play.travel` legs, the cast, the name pools). A world that wants its own work would export,
per settlement, a list of standing work in the same closed vocabulary — `{"work": "escort" |
"guard" | "carry" | "count" | "labour", "employer": <cast id>, "to": <settlement id>}` — and
the engine would price, place and time it exactly as it does the opening's.

## 5. Files touched

- `rules/cards.py` (`known`, `standing`, carriers, brief, Journal, take-up, write-back)
- `rules/hooks.py` (`render`'s carrier)
- `rules/schemes.py` (fresh schemes' quests open unheard; a step on a quest not taken
  carries `not_own`)
- `rules/engine.py` (`_op_quest` take-up, `_take_up`, `_op_track` quarry/follow, the
  follow's walk in `_drive`)
- `rules/intents.py` (`quest` and `track` signatures)
- `rules/tracking.py` (`quarry_of`, `same_ground`, `after`)
- `gm/planned.py` (`matter_slot`, `_not_their_goal`, `_holds_a_job`, `_no_job_made_up`)
- `gm/agent.py` (the pull dict to planned, the read-back callbacks, the free beat's cut,
  `quarries`)
- `gm/beat_verify.py` (`own_goal_sentence`, `invented_job_sentence`, a successful track
  that found nothing is not asked as an attempt)
- `gm/interpret.py` (`confirm_quarry`, `confirm_take_up`)
- `gm/acts_to_ops.py` (`follow` to `track`, merged into a look in the same sentence;
  `quarries`; `take_ups`; the plan's walk and the plan's own quest replaced)
- `gm/prompts.py` (the take-up line in the plan's quest rules)
- `play/views.py` (`note_heard`)
- `play/gm_answers.py` (quests answered as the Journal shows them)
- Tests: `tests/test_known_matters.py`, `tests/test_tracking_a_quarry.py`
