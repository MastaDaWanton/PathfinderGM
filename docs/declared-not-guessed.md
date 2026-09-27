# Declared, not guessed

*Design for the narration redesign, 2026-09-25. Phase 2 of the deferred list. Nothing here is
built until the user has read it; the open questions are at the end.*

---

## The problem, stated in the code's own terms

After every prose beat the app reads the finished text with regexes and changes the game
from what it finds. Eight doors do this today:

| door | where | what it writes | a recent misfire |
|---|---|---|---|
| `note_cast` + `promote_cast` | `play/views.py` `_finish` | books a person, stands them in the scene | the phantom "elder" from "the elder-quarter" inside a quote (2026-09-24) |
| `apply_introductions` / `named_in_apposition` | `_finish` | renames a person | "let's call it the stranger" (item 12) |
| `hailed_by` | `_finish` | opens a conversation | — (new 09-24) |
| `settle_descriptions` + `place_the_face` | `_finish` | writes a face into the beat | the elder's face inside Korgath's line |
| `joiners` | `_finish` | puts a bystander into the fight | — |
| `attacked_by` → `struck_first` | `_finish` | opens a fight and rolls an NPC's blow | six of six friendly sentences read as blows (2026-09-25) |
| `_found_from_the_page` | `gm/agent.py` `polish` | founds a place, moves the party | a smithy founded from a brawl (fixed 4e97cdb) |
| `unname_strangers` | `gm/agent.py` `_groom` | strikes a name from the prose | "Name's Vorn" rewritten in his own line (fixed 5927fc7) |

Each misfire was fixed where it was found, and each fix made the regex wider or narrower for
the next sentence nobody had written yet. The replay corpus (`tests/replay/`, phase 1)
measures how often each door fires on real model prose; the numbers are below.

## What the traditions do

Primary sources, gathered by the research pass of 2026-09-25 (full citations in the session
record; the load-bearing ones here):

- **No system found derives game state from its own finished prose.** Latitude's Voyage
  (six prototype engines before it shipped) keeps the world in an engine and "the AI turns
  that into the story"; Hidden Door keeps characters, places and objects as cards set up
  before play; Friends & Fables' engine decides when state changes and lets entity creation
  be switched off; Inworld sends structured triggers beside the dialogue.
- **The one measured comparison is against us.** Labyrinth (arXiv 2409.06949, GPT-4): new
  NPCs arrive by a `create_npc` function call; letting the model rewrite state from the
  dialogue was the WORST of the approaches tried, at 27% correct on their state tests. And
  giving the model only state functions made it over-call them — a warning for us.
- **Concordia** (arXiv 2312.03664) extracts state from a plain *event statement* the game
  master writes first — not from literary prose.
- **Forcing prose into JSON is unmeasured for creative writing.** Tam et al. (2024) found
  format constraints hurt reasoning and helped classification, with key order mattering;
  nobody has measured narrative quality. Our own data: gemma-12B broke out of long JSON
  strings three turns in four under a `minLength` grammar (`gm/prompts.py`), and segments
  would multiply the string boundaries.
- **Attribution after the fact costs about one line in ten.** Llama-3-8B attributes speakers
  at 81.8% on untagged quotes in published novels (arXiv 2608.02359). Tagging the speaker
  while writing avoids that error: the model knows who is talking.
- **Declared before use** is the common shape for new characters (Labyrinth, Dramatron,
  PANGeA, Hidden Door). **Inline speaker tags** are practice (Intra, Dramatron), not measured.

## The design

**The planner declares; the engine applies; the prose describes; the detectors check.**

1. **New people are declared in the plan.** A new op, `introduce{role, description,
   count, how: arrives|already_here}`, validated against the world (`rules/scope.py`,
   `names.appearance_for`, `faces`) exactly as `spawn` is. Refs `new1`…`new3` are reserved
   in the schema's enum so the same plan (and the prose) can refer to them. Everyone
   introduced is a bystander until they act or are acted on (item 18's ruling).
2. **NPC speech is tagged in the prose, not guessed.** The prose call writes dialogue as
   `<say who="c3">“You're a long way from the interior.”</say>` (and `to="you"` when it is
   aimed at the player). Tags are parsed in code against the scene's refs — an unknown ref
   is repaired, never booked — and stripped before the player sees the beat. This replaces
   `hailed_by`'s head-word guessing and gives `apply_introductions` a known speaker.
   Deliberately NOT a JSON segment schema (the grammar evidence above).
3. **A name given is read from tagged speech.** "Call me Kael" inside `<say who="c3">` names
   c3; the phrase detector stays, the speaker guess goes.
4. **Blows at the player are plan ops.** An NPC who strikes first does it as an `attack`
   intent with that NPC as actor (the engine's `struck_first` door already exists for this),
   declared by the planner or by the NPC-turn call. `attacked_by` stops opening fights.
5. **Places are founded by the plan.** `found{name, kind}` already exists and is
   world-checked by `places.fits_here`; the planner declares a place when the scene goes
   there. `_found_from_the_page` stops founding.
6. **The detectors become checks.** `note_cast`, `attacked_by`, `stands_elsewhere`,
   `unname_strangers` and friends keep reading the prose — but what they find now triggers
   the existing targeted-repair call ("somebody the scene does not have is in this beat:
   c3's line names 'the elder'…"), with the plain tells as the backstop. A misfire costs a
   rewrite, never a phantom in the scene. This is the project's own first rule — detect
   mechanically, repair with a targeted call — applied to the doors that broke it.

**Built one door at a time**, each measured on the replay corpus and a live audit before
the next: tags and hails first (smallest, and they unblock names), then introductions, then
blows, then places, then the booking door last (the biggest).

## Risks, stated

- **The planner must foresee.** A person who only turns up in the prose is now repaired out
  rather than booked. Scenes could feel emptier unless the planner learns to introduce
  people; the "Continue means the scene moves" ruling depends on it. Measured by the audit's
  texture report before and after.
- **A fatter plan schema** is the answering-N-things-in-parallel risk. Each new op is added
  alone and measured.
- **Tag compliance** by an 8-12B model is unmeasured anywhere; the corpus will measure ours.
  Untagged speech falls back to today's attribution (never to booking).
- Nothing measures prose quality under any option; the narrator audit on real play decides.

## Decided (2026-09-25)

- **The crowd:** nobody is booked from a sentence; everyone the prose describes is recorded
  as a located person (a "glimpse"), made real when the player engages them, residents
  persisting in their settlement — the full shape is `docs/the-population.md`.
- **Places:** the mechanism is free, the outcome is not — "as long as the creation of places
  is happening to allow for travel, questing and discovery." Founding stays on the prose
  path (outside fights) and gains the planner's `found`; the corpus measures that places
  still appear.

## Built: speaker tags (2026-09-25)

The first door. The prose call writes `<say who=c3 to=you>'…'</say>`. `speech.lift`
takes the tags out the moment any reply's narration is read: `GMAgent._lift` sits at
every reader, an AST test holds all of them to it, and the opening lifts its own.
The tags are checked against the people standing where the party is, never against
everyone in the save. An unknown ref attributes nothing and books nobody; its claim is
kept as `was` so the miss can be counted. `hailed_by` and `introduced_by` read the tag
first and fall back to the old guess for untagged lines. The beat keeps its
attributions as `said`, and every turn logs `speech-tags`: lines, tagged, refs naming
nobody here, and the hails the tags found beside the hails the guess would have found.

Prior art: Intra (Bicking, 2025) writes `<dialog from= to=>` inline, choosing text
markup over tools for narrative work. Nobody has published tag compliance for 8-12B
models, so these runs are the measurement.

**Live, gemma-4-12B, the town script, 12 turns each, from the game's own turn log:**

| | tags taught by the examples | + the model's own earlier beats shown tagged |
|---|---|---|
| quoted lines attributed on the page | 9 of 20 (45%) | 16 of 20 (80%) |
| tags naming somebody not present (refused, fell back) | 2 | 2 |
| hails the tag found and the guess missed | 2 | 4 |
| hails the guess found and the tag contradicted | 0 | 0 |
| tags reaching the page | 0 | 0 |

The first run tagged all or nothing per beat. The untagged beats followed tagged ones
that the prompt had shown back to the model with the tags lifted, so two beats of the
model's own untagged speech sat in front of it against the examples' tagged ones.
`speech.retag` writes the recorded tags back for the prompt only; every check still
reads the plain beat. Twelve turns is a small sample, and the direction is what it
shows.

The one tagged speaker who was wrong: the man tending a cart's crates in a field was
tagged as the gate's watchman, who was elsewhere. The check refused the tag, and the
fallback guess read "the merchant's cart" as the merchant who was standing there.

Both runs are in the replay corpus. It replays each draft against the scene from before
the turn, so its tag count is a floor: a person the turn's own plan spawned counts as
"nobody here".

Next door: names read from tagged speech are already live through `introduced_by`. The
`introduce` op comes next.

## Built: `introduce` (2026-09-25)

The second door. `introduce{who; count <= 3, how: arrives|already_here, template, zone}`
makes a bystander with a population record, a rolled life and a face, through
`population.embody`: the one door the prose's people, the finder's repair and the plan
now share. The same plan targets them as new1–new3, placeholders in the style of
JSON:API's `lid` and ReWOO's `#E1`. Each is legal only after the intent that makes it,
and is stamped at validation so the model cannot write it. The engine swaps real refs
into the queue as each person lands, so a turn suspended for a roll saves real refs.
`already_here` binds to the glimpse or actor the scene already holds before it makes
anybody. There is one `introduce` per plan: Labyrinth and When2Call both measure
over-use of an op that is always available.

**Live, gemma-4-12B, a ten-turn script where every line asks for somebody new
(`narrator_audit.py --script strangers`):**

| | run 1 | run 2 | run 3 | run 4 |
|---|---|---|---|---|
| turns where introduce ran | 2 | 9 | 9 | 8 |
| false "not here" refusals | 5 | 1 | 0 | 1 → fixed |
| turns lost | 0 | 0 | 1 | 0 |
| plan attempts for 10 turns | — | — | ~25 | 11 |

The planner under-used the op rather than over-using it: in the first run it wrote
`introduce` only where a turn was worded like the worked example. The fixes, each found
in one of these runs:

- **Trades were refused as absent.** "No scribe is here, and Zhilvarnia has none the
  world names", said of a city: the item-29 rule against conjuring the mayor had reached
  every trade. A trade or a description is now UNMET, and offices and unknown names keep
  the world's answer.
- **`person_sought`** read "ask around for a healer" as "a" + "round".
- **Scope matched on "the"**, so "the oldest person on the street" matched a guild leader
  in another city.
- **`inject_introduce`** declares the op when the player looks for somebody who isn't
  here, in a settlement, out of a fight. The schema's `must_contain` did not hold on half
  the turns, so the injector is also the net.
- **Leniency:** `how` and `who` are read, not refused. A blank `who` is filled from the
  player's words, and a long one is clipped.
- **The repeat check** read two introductions as "the same thing as last turn", because
  the net writes one `because` for all of them. It lost a turn.
- **Definiteness.** "a child" is any child: the population's here ring, then a new
  person. "the girl" is that girl, in every ring. This is the same Heim distinction the
  cast ledger uses, and the user's ruling that untied kinds should not always reuse.
- **The three invented-name faults of run 2** were our own face line ("is a Korvu:
  Somewhere in the middle of life"); the age clause is now lower-cased.

Not done: a trade the population rolled but the prose never showed still answers the
finder. In run 4, "a scribe" in the tavern found the man in the corner whom the
population had rolled as a scribe. That reads as the world being consistent; flagged to
the user.

## Built: blows as plan ops (2026-09-25)

The fourth door.

- **A blow the plan declares is rolled before the prose.** It is an `attack` with an NPC
  as actor. When somebody other than the player opens a fight, `Engine.run` rolls the
  initiator's blow in the same batch (`_their_first_blow`), so the prose describes what
  landed. `struck_first` is one run of that rule now; the opening effect carries the
  declared params.
- **The prose never opens a fight.** `attacked_by` is a check, run in `narrate_turn`. A
  blow the engine never rolled gets one targeted rewrite naming the fix. If it still
  strikes, the sentence is cut. This holds whether or not the striker is somebody the
  scene holds yet. `_finish` logs anything still read and opens nothing.
- A worked example shows the planner declaring an NPC's blow.
  `narrator_audit.py --script provoke` escalates verbally against one man; nothing the
  player does is itself an attack.

**Live, gemma-4-12B, the provoke script:**

| | run A | run B |
|---|---|---|
| turns where the plan declared his blow | 2 (turns 8, 9) | 0 |
| fights the prose door opened | 1, on "he slams a heavy, calloused fist onto the bar" | 0 |
| blows the new check had to rewrite | — | 0 |

A first version of the script knocked a drink from his hand. The planner read that as
the player attacking, so every turn after it was already a fight. The same line produced
"Kesst Vayr drinks." (the noun "drink" read as the verb), which is now fixed.

**What this leaves open, measured:** the man was insulted nine times in run B and never
struck. The prose built the tension correctly and waited ("He doesn't lunge, but his
knuckles turn white"). Nothing in the world moved: no insult changed anyone's attitude,
so the world has no route from provocation to violence, and the planner rarely takes the
step unprompted. This is a question of world logic, put to the user rather than guessed.

## Built: places by the plan (2026-09-26)

The fifth door, under the user's ruling that the mechanism is free and the outcome is
not: places must keep being created for travel, questing and discovery, and the prose
door stays alongside the planner's `found`.

- **A plan can found a place and walk into it in the same turn.** Validation checked
  the whole list before any of it ran, so "found The Tarred Rope, travel there" was
  refused because the place did not exist yet. It now projects the places earlier
  `found` intents will make, as `spawn` projects refs. A `travel` written before its own
  `found` has the `found` moved ahead of it.
- **A travel to an unknown place is refused with the fix named**: "found it first in
  the same plan", with the op spelled out. In the live runs this refusal taught the
  planner every place it founded: the first attempt was refused, and the retry founded
  and walked in.
- **A building hangs off the street.** A settlement kind founded from inside a building
  goes off the nearest place under the sky, up the chain or out through the interior's
  first exit. Live, before this: "the stables is a place now, off the shrine".
- **An empty travel takes the place the player named**, when the sentence names exactly
  one settlement kind. Live, twice: "I go looking for the bathhouse" became a travel to
  nowhere and "Nobody moves: where to?".

**Live, gemma-4-12B, `narrator_audit.py --script discover` (ten places to look for):**

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| places the plan founded | 4 | 3 | 3 |
| places the prose door founded | 0 | 0 | 0 |
| a building founded inside another | 1 (stables off the shrine) | 0 | 0 |
| travels to nowhere | 2 | 2 | 0 |

The replay corpus now counts `plans founding a place`.

Seen and not fixed: a plan that introduced a bookseller and then walked the party to the
guildhall, leaving him behind. That is the planner's coherence, not a door.
