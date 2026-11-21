# A town's trouble shown, not hung in the air (2026-11-21)

Lane fix/matter-shown, for 0.4.9.

The owner, 2026-11-21:

> "Tensions over water rights linger in the air like a heavy mist — I see the above phrasing
> very often and it would be more okay if I ever knew what was happening to make me feel
> the tension, please tell me what is happening that creates this tension instead of the
> general dilemma or the overarching problem."

The samples (before and after) are in `2026-11-21-matter-shown-samples.md`. The bench is §5.

## 1. What was measured before anything was built

Over the owner's 12 campaign saves (read-only copy, pgm-work/owner-1120-data):

- **20 of 964 GM beats** carry a "tension … hangs / lingers / palpable / in the air"
  sentence (the brief's own count script).
- **Which slot wrote them** (the turn log keeps each slot's raw reply; a slightly broader
  pattern than the count script, adding bare "in the air", "palpable", "hangs heavy" and
  "simmering"): the `matter` slot 14, the `still` slot 10 (it carries the last beat's mood
  forward), act slots 4, the free prose 3, repairs and polish 3.
- **How often a town's trouble is pulled:** 29 of 457 logged prose beats (6%) carried a
  world situation as the matter (`Ongoing friction over grazing land` and its siblings).
  In one save the same town's grazing land came back on beats 8, 39, 55, 73 and 79.
- **What the slot was given.** World Bible's strain cards are abstract by construction:
  "Ongoing friction over grazing land. Simmering, not yet at open conflict. … Tension in
  Harforge currently sits at a simmer — real, openly discussed, but not yet at open
  conflict." The slot was told "A matter of the world here … Let it touch the scene in one
  sentence, as something seen or heard here". It had nothing seen or heard to give, so it
  gave the abstraction back, with weather for colour.
- **The gold-prose writers found the same thing** (pgm-work/prose-gold, 19 matter slots):
  - 6 matter slots were pulled outside the town (a wood, the last sheds, standing water, a
    ridgeline) "with nobody present … an invitation to invent";
  - 7 had a travel tell pasted in as the matter's fact. `touch_from_outcomes` lands any tell
    that hits two of a card's loose keys on it, and a strain card has 40-70 loose keys
    ("trade", "local", "land", "season");
  - 3 named another town's trouble.

## 2. What the traditions say

Sources were read directly unless marked.

- **Dungeon World, Gamemastering** (dungeonworldsrd.com/gamemastering). One GM move is
  "Show signs of an approaching threat", glossed "you just show them that something's going
  to happen unless they do something about it". The principle "Address the characters, not
  the players" keeps the table in the fiction.
  - **Taken:** the matter slot's job is a sign, something the character can see or hear,
    never the GM's summary of the threat.
- **Dungeon World, Fronts** (roll20.net/compendium/dw/Rules:Fronts). Grim portents are
  "dark designs for what could happen if a danger goes unchecked". The examples are short
  events ("The College sends an expedition to the Gate"). They are "possible moves waiting
  in the wings". When a portent advances, you "show its effects".
  - The page does not say "visible", but it does ask the GM to "give it a concrete form in
    your front", which supports the reading here.
  - **Taken:** each showing is one small event or trace, a change you could point at.
  - **Not taken:** portent ladders that advance the danger. World Bible exports no steps
    for a strain, and the strain's clock is not moved by being shown. A shown incident is
    colour from the situation, not progress of it.
- **The Alexandrian, "Don't Prep Plots"** (thealexandrian.net/wordpress/4147). Prep "a set
  of circumstances", not "a sequence of events". The example is concrete: two ships, a
  derelict the navy will spot at a set time, villains hidden in a temple.
  - **Taken:** the town's trouble is a situation, and a situation is made of things that
    are there (a locked cistern, a tally on a post). It is not a mood.
- **The Alexandrian, "Running the City"** (thealexandrian.net/wordpress/48182). A city's
  scenic encounters convey "the constant activity", "stuff happening all the time and just
  out of sight". Handcrafted ones "you'll need to periodically restock … as they get used
  up". They are keyed so districts feel distinct.
  - **Taken:** the restocking. An incident once shown is used up, so the next showing of
    the same trouble must be a different one.
  - **Taken:** "just out of sight". A sound through a wall, a notice, a lock or a trace
    shows activity without putting a new person on the page.
- **Non-focal and past encounters** (Sly Flourish, slyflourish.com/non-focal_random_encounters,
  crediting Justin Alexander for non-focal). Encounters "don't necessarily happen to the
  characters". A past encounter is found by its traces ("signs that a huge reptile crashed
  through the underbrush").
  - **Taken:** traces as a first-class kind of incident. They need no actor, so they cannot
    break the "seen people are real" ruling.
- **Blades in the Dark, Progress clocks** (roll20.net/compendium/BITD/Rules:Progress
  clocks). A clock "reflects the fictional situation, so the group can gauge how they're
  doing". "A clock is like a speedometer in a car": it "doesn't determine the speed".
  - **Taken:** the fiction carries the situation, and the record follows it. A strain shown
    is not a strain advanced.
  - The page says advancing faction clocks means "things happen that they're not directly
    connected to", which changes the situation. **Could not source** any method for how
    that progress is shown in the fiction.
- **Worlds Without Number** (Kevin Crawford). Its settlement and adventure tags come with
  enemies, friends, complications, things and places.
  - **Secondhand only:** a table of contents on a shared document, and a Go reproduction
    of the tables. The book itself was not read.
  - **Taken in spirit:** a trouble is shown by a thing or a complication, not by its name.
    The codebase already uses WWN-style tags for dungeons (`rules/dungeons.py`).
- **Apocalypse World fronts.** Not read directly. Dungeon World's fronts descend from them,
  and the Dungeon World text above is what is used.
- **Data-to-text grounding** (Kasner & Dušek, ACL 2024, aclanthology.org/2024.acl-long.651,
  as read by the sibling travel-prose lane). With thin inputs, open models "tend to
  introduce extra information". A strain card is about as thin as an input gets.
  - **Taken:** the slot is given the place, the hour and the people here (THE SCENE
    already holds them) and asked to choose one concrete thing from them. What it writes is
    checked in code.
- **"Echoes in AI"** (arxiv.org/abs/2501.00273, as cited by the travel-prose lane). Model
  stories repeat their elements across generations.
  - **Taken:** each showing is remembered on the card, the next showing is told what was
    already shown, and a repeat is found in code.
- **Show, don't tell in model prose.** No paper was found that measures stated versus
  dramatised emotion in model prose. The search turned up homogeneity and story-quality
  work only. **Could not source.**

**Advised against** (no source found that a tradition tried this and then dropped it):

- **"Remote-control boxed text"** that declares "the thoughts or feelings … of the PCs"
  (The Alexandrian, GM Don't List #13, thealexandrian.net/wordpress/48312, read directly).
  "A tension you can feel in the air" has exactly this shape.
- **Used encounters left in place.** "Running the City" says handcrafted encounters must be
  restocked "as they get used up". It says nothing about what happens if they are not.

A second pass (a critic re-reading every primary URL above) confirmed the quotes. It
corrected four claims: "concrete" is on the Fronts page; the speedometer wording; what the
Blades page says of faction clocks; and the framing of this list.

## 3. Options weighed

1. **The model writes a batch of incidents per town, cached.**
   - **Rejected.** A model asked for N things answers in parallel (CLAUDE.md's five-factions
     lesson). A batch is also stale before it is used: the batch cannot know where the
     party will be standing, so an incident at the well is wrong in the tavern.
2. **An authored table of incidents per kind of dispute** (water, grazing, toll, cult…),
   picked by a schema-constrained model reading the strain into a closed enum.
   - **Rejected for now.** It is world-agnostic only for the kinds we list, and World
     Bible's strains are open-ended ("a border shrine both sides claim", "an old unpaid
     blood-debt", "Who pays to keep the ford stones in place"). Fifty authored lines would
     be generic across every town of a kind.
3. **The matter slot itself shows one incident, here, now, with demonstrations; code
   checks it; the card remembers what was shown.** **Chosen.**
   - It is one call, as before.
   - The slot already sees THE SCENE: where the party stands, the hour, and PEOPLE HERE
     NOW. So the incident fits the spot, and any person in it is a person who is here.
   - The shape comes from demonstration, not instruction: three synthetic examples, from no
     world, turned over between beats (least recently used), checked for leaks
     (`demo_leak`).
   - Code checks the result: the abstraction (`told_not_shown`), a repeat of an earlier
     showing (`copied_from` against the card's `shown`), and the existing read-backs. A
     fault is asked again with the fault named, and a matter slot still at fault is dropped.
     Nothing on the page beats something abstract on the page.
   - What was shown is kept on the card (`Card.shown`, version-stamped `shown_v`, last
     `SHOWN_KEPT`). It lives in the campaign save, so a version bump forgets it, as
     CLAUDE.md asks of derived caches.
4. **Frequency, at the source** rather than by a counter:
   - A world situation with nobody of its own is pulled only **inside its own settlement**.
     This removes the wood, the ridgeline and the other town.
   - It is "spoken" only by its **identity** words, the same narrowing `identity_keys`
     already made for "recent" after the sixty-turn run. Two loose keys in a tell are no
     longer enough.
   - Engine tells no longer land on it by loose keys, so its facts stay the world's own.
   - Once shown it rests (`mentioned`) even though the incident shares no word with the
     card's title. Before, a showing that did not repeat the title words never started the
     rest.
5. **The other slots** (`still`, the acts, the aside) also wrote the mood, 14 times between
   them, because the brief carries the strain on every turn. The same detector runs on
   every non-reply slot. The slot is asked again with the sentence named, and the sentence
   is cut if it is still there and the slot has others.
   - A reply is left alone: a person saying "tempers are short over the well" is talk, and
     talk is how a trouble is heard.
   - **Not taken: removing the strain from the brief.** A person asked "what's wrong here?"
     needs it to answer from.

## 4. Owner calls made by default

See the lane report. In short:

- a world trouble is never pulled outside its settlement;
- a matter slot that still states the mood after one retry is dropped, not shown;
- a shown person must be someone in PEOPLE HERE NOW; anyone else the beat shows is the
  seen-people door's to make real, as ruled;
- the strain stays in the brief.

## 5. The bench

**Setup.**

- 32 town beats per arm, paired, run in-process through `/api/say` (scratch driver:
  pgm-work/matter-bench/bench.py, on tools/narration_diag/drive.py).
- Two worlds:
  - Aurvantis: Balzun's gate, Fizspark's market and Scrapden's tavern, from three testers'
    saves;
  - Pangrella: Mirabalos's warrens, a fresh campaign.
- Eight ordinary lines on each snapshot ("I look around.", "I sit down and rest for a
  bit.", and so on).
- The town's own trouble was **forced** as the matter on both arms when the engine would
  not have picked it, so each pair shows the same trouble on the same beat.
- Before is aa5df0c6; after is this branch at b95688de. Both used the same Ollama seed per
  call.
- Two blind scorers scored all 64 items, with arms hidden and shuffled. They scored:
  - S: is the trouble shown as something concrete here?
  - E: errors, split into P (a person not present), N (a name no fact gives), I (an
    invention that does not fit) and C (a contradiction);
  - Q: prose quality, 1-5.

  They agreed on S for 64 of 64 items, and on has-an-error for 63 of 64.

**Mechanical** (`told_not_shown` over the whole page):

| | before | after |
|---|---|---|
| beats with a mood-in-the-air sentence | 13 / 32 | 0 / 32 |
| matter slot on the page | 27 | 27 |
| seconds a turn, mean (median) | 69 (60) | 51 (46), shared GPU |

**Blind** (after minus before, paired, 95% bootstrap intervals):

| scorer | trouble shown (S) | errors a beat | prose 1-5 |
|---|---|---|---|
| A | 0.00 -> 0.84 (+0.84, +0.72..+0.97) | 0.31 -> 0.06 (-0.25, -0.41..-0.09) | 2.19 -> 3.03 (+0.84, +0.62..+1.06) |
| B | 0.00 -> 0.84 (+0.84, +0.72..+0.97) | 0.28 -> 0.09 (-0.19, -0.38..-0.03) | 2.03 -> 2.88 (+0.84, +0.66..+1.00) |

**Reading it.**

- **The trouble is now shown.** Before, no beat showed anything of it: the old slot wrote
  either the mood, or crowds of whispering merchants and huddled nobles who were not in
  the scene.
- **Those crowds were most of the "before" errors.** They were P: 10 of scorer A's 10
  errors and 8 of scorer B's 9.
- **What is still wrong after:**
  - 2 or 3 people not present in all, mostly a companion's line about "scanning the crowd";
  - the 5 beats of 32 that show nothing of the trouble. There the matter slot was dropped
    in both arms, by the budget or when the reply took the beat.
- **Seconds are not a finding.** Other lanes shared the GPU.

**What the bench did not test** (the samples file says the same):

- **Rotation.** Every beat started from a fresh snapshot, so `Card.shown` was always
  empty. Within a town the model settles on one shape: a notice "pinned to a nearby
  post" on 7 of 8 Fizspark beats, and a "fresh, jagged mark" of a crest on 5 of 8 in
  Mirabalos. Rotation is covered by tests and by one live showing, not by a model chain.
- **The cause-not-mood fact.** It came after the bench. The after arm was still handed
  "Tension in Fizspark currently sits at a simmer" on 14 beats, and wrote no mood on any
  of them.

**Frequency** (pgm-work/matter-bench/replay_freq.py). Every player turn of the 12 owner
saves was replayed through `thread_to_pull` on each arm's code, with the real beats as
the write-back:

| arm | turns that pulled a world trouble | pulled outside its own streets |
|---|---|---|
| before | 28 / 495 (5.7%; the turn logs say 29 / 457, 6%) | 22 of the 28 |
| after | 4 / 495 (0.8%) | 0 |

- Inside a town the trouble came up 6 times before and 4 after.
- Most of the "very often" was the trouble following the party out of town: into the
  fields, the forest and the next town.
