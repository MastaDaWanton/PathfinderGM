# Who the prose means

*Design note, 2026-09-28. The next step of `docs/declared-not-guessed.md`. Nothing here is
built until the user has read it; the open questions are at the end.*

---

## The problem, stated in the code's own terms

The engine never loses track of who is who. Every person has a ref (`pc`, `c2`, `c3`),
minted once and never reused, and the turn log records every intent and outcome by ref.
In the 2026-09-27 manoeuvre run the thug was `c3` from spawn to the last turn and Borin
Lyraxys was `c2`, and no roll, tell or condition ever crossed between them.

The prose is where "who" goes soft. The narrator writes names and descriptions ("the
brute", "the warrior", "Borin"), and about a dozen checks then **guess** which ref each
one means from the words:

| check | what it guesses | a measured misfire |
|---|---|---|
| `wrong_actor` (never-named rule) | whether the beat names the creature whose turn it is | 3 of 3 flags in the 2026-09-27 run were sound beats calling the actor "the warrior", "the Korvu" |
| `cut_dead_men_walking` | whether a sentence has a dead man acting | cut the LIVING thug's groan because a dead man was also "thug" (docs/wrong-actor.md) |
| `creature_nouns_for_pc` | whether "the beast" means the player | swapped the enemy's own noun for the player's name, 4 of 5 flagged beats (docs/wrong-actor.md) |
| `apply_introductions` | whose name a name in the prose is | gave `c3` ("new") the first name of `c2`, the other man in the room; he fought as "Borin" beside "Borin Lyraxys" (2026-09-27 run, most likely this door — not yet pinned by a replay) |
| `wrong_hands`, `hailed_by`, `settle_descriptions`, `note_cast`, `joiners` | who a blow, a hail, a face or a person in a sentence belongs to | catalogued in docs/declared-not-guessed.md |

Each misfire was fixed where it was found, and each fix widened or narrowed a guess for the
next sentence nobody had written yet. That is the pattern `declared-not-guessed.md` set out
to end; speaker tags ended it for speech. This note proposes the same for every mention.

## What the traditions and the literature say

Research pass of 2026-09-28, checked by a critic pass and then spot-checked by hand.

- **Declaring while writing beats matching afterwards, in the one clean comparison
  found.** ALCE (Gao et al. 2023, <https://arxiv.org/abs/2305.14627>): ChatGPT citing
  sources inline while writing scored 73.6 recall / 72.5 precision; the same model's text
  cited after the fact scored 26.7 / 26.7 — "texts that are correct but not similar to
  any retrieved passages, making it difficult to match a citation post-hoc". A caveat
  stated plainly: the post-hoc condition also wrote without the sources in front of it,
  so the gap is not only about when the reference was declared.
- **Guessing afterwards has a ceiling even for purpose-built tools.** Coreference on
  fiction reaches about 80 CoNLL-F1 on LitBank excerpts and 67.0 on whole books
  (BookCoref, <https://arxiv.org/html/2507.12075>); quotation attribution by Llama-3-8B on
  published novels is 89.8% overall, 81.8% on implicit quotes
  (<https://arxiv.org/html/2608.02359>). Those are human-written novels; our own guesses
  run on model prose with none of that tooling.
- **Small models comply poorly with markup taught only by examples.** LLaMA-2-7B citing
  from demonstrations alone scored 14.1 / 15.3 (Huang et al. 2024,
  <https://arxiv.org/html/2402.04315>); on a coreference-markup task LLaMA3-8B "often
  failed to understand the complex structure of the prompts"
  (<https://arxiv.org/html/2409.13555>, annotating existing text, not writing it). The
  most relevant number anywhere is our own: speaker tags on gemma-4-12B went from 45% of
  quoted lines tagged with examples alone to **80%** once the model's own earlier beats
  were shown back tagged (`speech.retag`), with 0 tags reaching the page.
- **Inline markup over tools for narrative work** is the practice of Intra (Ian Bicking,
  <https://ianbicking.org/blog/2025/07/intra-llm-text-adventure>): `<dialog from= to=>`
  inline, because "in practice LLMs seem to change their behavior or lose some of their
  broader intelligence when using a tool". He publishes no compliance rates. (A quotation
  the research pass first attributed to him could not be found on the page and was
  replaced with this one.)
- **Name-keyed matching fails in the ways ours does.** AI Dungeon's Story Cards fire on a
  substring (`cat` inside `catalog`; <https://help.aidungeon.com/faq/story-cards>);
  SillyTavern's key "AI" fired on "ain't" and "Maine" until "match whole words" was added
  (<https://github.com/SillyTavern/SillyTavern/issues/386>). Neither measures a rate.
- **Whether markup inside prose hurts the prose is unmeasured.** "Let Me Speak Freely"
  (Tam et al. 2024) found whole-answer JSON/XML formats hurt reasoning on Llama-3-8B;
  dottxt disputes it with matched prompts. Neither is about tags inside narrative.
- **Could not source:** a compliance rate for inline entity tags in *generated* prose from
  any 7–14B model; any evidence that tagging reduces a model's own who-did-what errors;
  a controlled XML-versus-bracket comparison for inline tags; anything published by Hidden
  Door, Latitude or Inworld on their markup. No system was found that tagged entities
  inline and then abandoned it — which is absence of evidence, not evidence.

## The design

**The narrator tags every person it mentions; code lifts the tags before anything reads the
prose; the checks read the tags; the player never sees a ref.**

1. **The tag.** The same attribute grammar the model already writes for speech:
   `<p who=c3>the thug</p>`. It wraps a name or a noun phrase for a person present —
   "Borin Lyraxys", "the brute with the marked knuckles". Pronouns are not tagged. "You"
   is never tagged: it is always the player.
2. **The words stay the model's.** Lifting keeps the text inside the tag exactly as
   written and throws the tag away. Nothing is substituted for a ref — substituting names
   is what `creature_nouns_for_pc` did, and it wrote the player's name onto the enemy.
3. **One door.** `speech.lift`, called from `GMAgent._lift` at every reader (an AST test
   already holds all readers to it), lifts `<p>` beside `<say>` and returns the mentions
   with their offsets into the plain beat. Refs are checked against the people standing
   where the party is, the placeholders `new1`–`new3` resolve to the people the same turn
   introduced, and an unknown ref attributes nothing and is counted — exactly as speaker
   tags are handled today.
4. **Shown back tagged.** The model's own recent beats are shown to it with their tags
   restored, for the prompt only (`speech.retag`'s move), because that is what took speaker
   tags from 45% to 80%.
5. **The checks read tags first and guess only what is untagged.** Each check keeps its
   guess as the fallback for an untagged mention, so a beat the model forgot to tag is no
   worse off than today.
6. **A new mechanical check: the words and the tag disagree.** `<p who=c3>Borin</p>` when
   `c3` is not Borin, or `<p who=c3>Kesst</p>` for anyone but the player, is detectable
   in code, and gets a targeted repair like every other detector.
7. **Where the player sees refs:** nowhere in the story. The sidebar's scene board already
   prints each person's ref in small type beside their name (`02-state.js`, `#board`),
   which is the one place the user allowed.

## What each check gains

| check | reads from the tags | expected effect |
|---|---|---|
| `wrong_actor` | whether any mention is the acting ref | the three false flags of 2026-09-27 ("the warrior", "the Korvu") become clean |
| `cut_dead_men_walking` | which ref the acting mention is | the living "thug" is no longer cut for a dead one |
| `creature_nouns_for_pc` | whether "the beast" is tagged as `pc` | swaps only a noun the model itself tagged as the player |
| `apply_introductions` | whose name is given | a name lands only on the ref it was said about |
| `wrong_hands`, `hailed_by`, `settle_descriptions` | who a blow, a hail, a face belongs to | the same, one at a time |

## Built in stages, each measured before the next

0. **Now, independent of the rest: a name cannot be taken twice.** A name read from the
   prose is refused for anybody if another person present already answers to it, whole
   or in part, and the refusal is logged. Mechanical, small, and it would have stopped
   "Borin". It does not wait on tags.
1. **Tag, lift and log; nothing reads the tags yet.** Teach the tag by the examples, show
   the model's beats back tagged, lift at the one door, and log per beat: person mentions
   found by today's guesses, mentions tagged, tags naming nobody here, tag/word
   disagreements, tags reaching the page (must be 0). Measured on the fight and town
   scripts, gemma-4-12B, twelve turns each, beside the same runs untagged: tag coverage,
   beat length, the audit's texture report, and seconds per turn.
2. **The checks switch to tags, one at a time**, `wrong_actor` first (it has the live
   false flags to count), each replayed through the corpus and a live run before the next.
3. **The disagreement check becomes a repair.**

The gate between stage 1 and stage 2 is the user's call on the numbers, not a number
written here in advance.

## Risks, stated

- **Coverage.** Speaker tags took an extra demonstration pass to reach 80%, and a mention
  is a smaller, more frequent thing than a line of dialogue. Untagged mentions fall back to
  today's guesses, so low coverage costs the benefit, not correctness.
- **Prose quality.** Unmeasured anywhere. Stage 1 exists to measure it before any check
  depends on it.
- **Wrong tags.** A tag naming the wrong person present would be believed where a guess
  might have been right. The disagreement check (step 6) catches the cases where the
  words give it away; the rest are counted in stage 1 by reading beats by hand.
- **Token cost.** About six tokens a mention; measured in stage 1 as seconds per turn.

## Not in this plan

- **Tells carrying refs and rendered per reader** — the Inform move taken all the way,
  so the engine's own sentences would never need `pc_to_second_person` either. Worth its
  own note once mentions are measured.
- **Pronouns.** "He" and "she" stay untagged; tagging them is the coreference task the
  literature says 8B-class models fail at.

## Open questions for the user

1. Stage 0 can go ahead on its own now. Do it?
2. The sidebar shows refs today. Keep that as it is, hide it, or show it only on hover?
3. After stage 1: what coverage would you want to see before the checks start trusting
   tags?
