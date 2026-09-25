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
