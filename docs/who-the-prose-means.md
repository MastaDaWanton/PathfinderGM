# Who the prose means

*Design note and record, 2026-09-28. The next step of `docs/declared-not-guessed.md`.
The user asked for stages 0-3 the same day; what was built, and why it is not the
design first written here, is in "Built" below. The code is `gm/mentions.py`, the
checks in `gm/narration.py` and `gm/judgement.py`, the wiring in `GMAgent._groom`; the
tests are `tests/test_a_name_taken_twice.py` and `tests/test_who_the_prose_means.py`;
the bench is `tools/mention_bench.py`.*

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

## The first design, and why it was not built

The first version of this note had the narrator write `<p who=c3>the thug</p>` around every
person it mentioned, as it already does `<say who=c3>` for speech. The user asked whether
there was another way than demonstration to get a small model to comply. There was:

- **Code finds the mentions and settles what is certain.** A name whose words belong to
  exactly one person here needs no model at all.
- **One short call labels the rest, as a multiple choice.** Each mention's answer is an enum
  of the refs present plus `nobody` — a construct this stack enforces (required properties
  and enums held 6 of 6 on 2026-09-27; `contains` held 0 of 6). The narrator writes plain
  prose, so the unmeasured risk to prose quality is gone, and a model that forgets a tag is
  no longer the failure mode.
- The price is labelling *after* writing, which lost to inline citation in ALCE — but that
  condition wrote without its sources, and the labeller here is shown the cast and the tells.
  Inline tags (the first design) stay unbuilt and unmeasured; the labelling measured good
  enough that they were not needed to finish the stages.

## Built

**Stage 0 — a name cannot be taken twice** (`judgement._answers_to`). A name read from the
prose is refused for anybody when every word of it belongs to one other person present,
shown or true, living or dead, and the turn's repairs say so. "Borin" beside "Borin
Lyraxys" is refused; "Bren Varn" beside "Aldo Varn" passes.

**Stage 1 — attribution** (`gm/mentions.py`). In the narration only (speech is a character's
to say): names of the people present, and descriptions — a determiner, up to three
describing words, a person noun (the cast roles, the creature nouns, and every descriptor
head, template and people's name present). `_groom` attributes once, after the rewrite; a
sentence changed after that is not in the attribution and its checks fall back to their
guess. Each groomed beat logs a `mentions` row. Off in the test suite, as the interpreter is.

**Stage 2 — the checks read it first, and guess only when it has no answer:**

| check | what it asks the attribution |
|---|---|
| `wrong_actor` / `right_actor` | whether the beat mentions the actor — only True is taken, so it can clear the never-named rule and never arm it |
| `cut_dead_men_walking` | whether the words that matched a dead name mean a living person here |
| `creature_nouns_for_pc` | whether "the beast" means the player — swapped only then |
| `apply_introductions` | who the head noun of an apposition ("The man—Korgath Varn—") is |

**Stage 3 — a name on the wrong person** (`Mention.misnamed`, `GMAgent._repair_misnamed`):
the code's name and the labeller's answer disagree. One targeted rewrite of the flagged
sentences, kept only if the wrong name is gone; no mechanical swap under it, because the
flag is the labeller's word against the name's, and a swap on a wrong flag writes the wrong
name — `creature_nouns_for_pc`'s fault exactly.

## Measured

**On the replay corpus** (`tools/mention_bench.py`, 142 recorded beats, gemma-4-12B heretic):

| | first pass | after the fixes below |
|---|---|---|
| mentions found | 353 | 335 |
| settled by code, by name | 11 | 11 |
| label call, median / max | 0.56 s / 1.43 s | 0.54 s / 1.36 s |
| a graded random 45: right / wrong / can't tell | 37 / 4 / 4 | 40 / 3 / 2 |

The graded misses were mostly one shape: somebody new, described in passing, put on
whoever was listed ("a man with a scarred hand … arguing with a merchant" → the servant).
The corpus replays each beat against the scene from *before* its turn, so a person the
turn's own plan introduced is missing from the list; the rate in the app, which attributes
after the plan, should be lower. A demonstration of a newcomer answered `nobody` moved it
only a little. The fixes between the passes: the finder dropped "that" and the possessives
as determiners ("missing his guard by a hair", "something that makes the nearby crowd
flinch") and stopped bridging over function words ("a panicked scuffle as people"); a
surname beside an unknown capitalised word is no longer certain ("the ostler, Lyraea
Lyraxys" was settled as Aethorin Lyraxys).

**`wrong_actor`, on real prose:**

- The three false flags of the 2026-09-27 manoeuvre run ("As the warrior turns to flee…",
  "The Korvu lunges forward…", "…against the intruder's grip…"), replayed with the live
  labeller: **3 of 3 cleared**. The cast was rebuilt by hand from that run's log, which did
  not save the scene.
- The committed corpus's six flags, against their recorded scenes: the **five beats turned
  round all stay flagged**; the sixth, sound but written only in pronouns ("He shifts his
  weight…"), stays flagged too — pronouns are not attributed, by design.

**Live, the fight script, 12 turns, labeller on and off** (`tools/narrator_audit.py`): on,
21 beats attributed, 35 of 35 mentions labelled, 0.75 s median per call, 0 misnamed, one
`wrong actor` rewrite — a beat that named nobody at all ("The heavy fist slams into the
counter just inches from your hand … his blow"), which the attribution cannot help with.
The on run scored 7 of 12 clean against the control's 10 of 12, and that is the scene, not
the labeller: the two campaigns rolled different towns, the control's "biggest man" was a
4-hp drover who died on turn 6, the on run's was Borin Lyraxys at 23 hp who was still
standing at turn 11, and all five `combat-turn-did-nothing` turns are the script's peaceful
lines (stand over him, take what he carried, walk out) inside a fight that had not ended.
Other sessions were using the same Ollama during both runs, so their timings are not clean.

**Not exercised live:** stage 3 (no misnamed flag in the corpus or the run — the corpus
predates the backstop fix that used to write names onto the wrong person, so its precision
is unmeasured), the dead-man spare, the beast swap and the apposition lookup. Each is held
by a test naming its defect.

## What it costs

One short call per groomed beat that mentions anybody, on the model already loaded: about
0.5–0.75 s. A creature's turn, which made one call after its prose, now makes two.

## Risks, stated

- **A wrong label is believed.** Every consumer is written so a wrong label errs toward the
  old behaviour or toward doing nothing: `wrong_actor` only clears, the dead-man cut only
  spares, the beast swap only declines, and the misname repair has no mechanical fallback.
- **Newcomers put on somebody listed** is the known error: 4 of the 90 graded labels. The
  other misses were one each: a place name ("the merchant's row" given to the merchant),
  prose that contradicted itself ("The man at the bar, a sturdy woman…"), and the shared
  surname, since fixed.
- **Pronouns** are not attributed; a beat that names nobody still costs a repair.

## Open questions for the user

1. The sidebar shows refs today. Keep that as it is, hide it, or show it only on hover?
2. Inline tags (the first design) were not built. Worth measuring against the labeller, or
   leave it?
