# Situation cards

*Design record, 2026-09-06. The code is `rules/cards.py`; the tests are
`tests/test_cards.py`; the export contract is `play.cards[]` in
`docs/campaign-format.md`.*

## The problem

"I notice that the situation with the woman and her supplies starts out somewhat
consistent. However, as I seal the jar it seems to lose the initial situation."

A language model has no memory of a situation. Every turn it rebuilds the world from
the text in front of it, and whatever is not in that text stops existing. The
research names it drift — models "must implicitly reconstruct world state from
dialogue history at each turn, leading to drift and contradiction accumulation"
(*Can LLM Agents Stick to the Script?*, 2026) — and measures where it bites worst:
factual tracking and time (*Lost in Stories*, Microsoft, 2026). Asked to infer D&D
game state from 800,000 real dialogue turns, a fine-tuned model got it right 58% of
the time (Callison-Burch et al., EMNLP 2022). The model cannot be the keeper of the
situation.

## What the traditions did

Every tradition that beat this did the same thing: stop asking the model to
remember, and hand it a small written record that something else keeps.

- **Fate** writes *situation aspects* on index cards on the table; they sit there
  until somebody changes or removes them.
- **Blades in the Dark** adds a *progress clock*: how close the situation is to
  changing, ticked by what people do.
- **Inform 7** makes a *scene* an object with a begins-when and an ends-when, so the
  program knows which situation it is in and cannot wander out by accident.
- **AI Dungeon (Story Cards), NovelAI (Lorebook), KoboldAI and SillyTavern (World
  Info)** all deliver notes the same way, and their official documentation agrees on
  the mechanism: each note has trigger keys; the last few turns are scanned for the
  keys; matching notes are inserted in front of the model, most relevant first, within
  a token budget; "always on" pins a note; the note leaves when its keys stop
  appearing. KoboldAI documents that an inserted note does not trigger further notes
  (no chaining); SillyTavern adds recursion as an option.
- **Generative Agents** (Park et al., 2023) kept the memory half: a log, periodic
  short reflections, and retrieval of the few entries that are recent, relevant and
  important — a handful of lines beats the whole history.

## What was built

A **card** is: an id, a title, up to eight facts, trigger keys, hierarchical tags,
the people it concerns (actor refs), the place it belongs to (a place id, the same
`Actor.at` coordinate everything else uses), a stage (`open`, `moving`, `resolved`,
`dropped`), a clock, provenance, a secret flag, an always-on flag.

**Where cards come from** — never from the model directly:

| Origin | Card |
|---|---|
| `opening` | the errand the player is standing in: why they came, what they are doing, what is already happening, with the person beside them; always on |
| `world:<id>` | authored by World Bible in `play.cards[]` (not written yet); and, derived from every export today, the starting settlement's strain from its own `Tension`/`Cause` facts, and each `unwritten` hook as a secret card |
| `engine:<op>` | facts that land from the engine's own tells — a tell naming one of the card's people, or hitting two of its keys, goes on the card |
| `watcher` | every three resolved turns the off-turn model reads the last beats against the live cards and proposes, per card, keep / advance with one fact / resolve, and at most one new card; a validator refuses a fact with a digit, a second sentence, or a name the world does not know, and a card the engine moved meanwhile is left alone; resolving pays the story award's advance share |

**How they reach the model.** `prompts.scene_brief` carries a SITUATIONS block:
the always-on card at this place first, then live cards whose keys appear in the
last three beats and the player's line, then cards resolved within the last three
turns, within a 1,400-character budget. The plan call sees secret cards; the prose
call never does.

**How they move.** A tell that names one of the card's people ticks the clock and
moves the stage from `open` to `moving`; a full clock resolves the card and takes its
grants off. Facts are deduplicated and capped at eight.

**The three laws.** Tags are the one vocabulary (`situation.*`, prefix-queried
through `states.matches`). A card that grants a state to a person does so as an
`ActiveEffect` with source `card:<id>` through `Actor.apply_effect`, and resolving the
card removes it — one applicator. Facts arrive from tells, the opening, the export or
a validator; the model writes none — severed tells.

## Refused, with reasons

- **The model as the keeper of the card.** 58%.
- **Chaining (an activated card's text triggering others).** KoboldAI's documented
  limit is a fine first design; SillyTavern's recursion is a later option if the
  table grows.
- **Embedding retrieval.** Keyword scanning is what every shipped lorebook does, is
  deterministic, and is checkable by reading the card.
- **Unbounded cards.** Eight facts, three beats of scan, a character budget. The
  Stanford result: a handful of relevant lines beats the whole history.

## Open

- A card's own `grants` used by a shipped card — the door exists and nothing walks
  through it yet.
- World Bible writing `play.cards[]`.
- The validator's trade on leading words: an advancing fact is checked with its first
  word lower-cased ("Work is scarce." is not somebody called Work), so a stranger
  who leads such a sentence slips onto a card; a new card's title and facts are
  checked strictly unless the leading word was said at the table as a plain word.


## Quests (added 2026-09-07)

A quest is a card of kind `quest`, tagged `situation.quest`, with objectives to tick, a
giver and a promise in words; the log on the table page reads it by that tag. See
`docs/quests-and-outfitting.md`.
