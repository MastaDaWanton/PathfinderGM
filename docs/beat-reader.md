# The beat reader

*Design record and measurements, 2026-10-03. Lane N of `docs/structured-turn.md` (the
Backward section). The code is `gm/beat_reader.py`; the appliers are
`play/aftermath/seen_people.py`, `speaker_real.py`, `places_heard.py`,
`mentioned_elsewhere.py` and `pronouns_adopted.py`; the bench is
`tools/beat_reader_bench.py` over `tests/beat_reader/gold.py`.*

The owner, after a day of regexes that each fixed one phrasing and missed the next: *"we
cant really depend i think on just layering mechanical detection logic on top this will be
an endless loop"*, then *"build it all the way through"*.

## What the regex harvesting cost on 2026-10-03

All live, gemma-4-12B, the owner's saves:

| beat | what the prose said | what the harvesters did |
|---|---|---|
| smithy | "The man at the workbench—the smith— … He is a large man" | made a second smith, c15, who then joined the conversation |
| market | "a grumpy man" inside the man in the heavy coat's own speech | read as him naming himself; the answer was cut |
| market | "'The Forge of the Broken Tide,' … 'Follow the main quay until you hit the turn for the wharf … the back of the smithy'" | two heard-of places, neither with a landmark |
| market | 'The say "just trying to start a conversation…" is a Korvu' | a person named `say "just trying…"` (c4) |
| market | six beats of "the man" speaking | every line booked to the servant carrying jugs |

Each needed one more regex. The beat reader replaces the reading, not the regexes one by
one.

## Prior art, and what was adopted or refused

Research pass of 2026-10-03. Primary sources where the page could be read; where a claim
could not be confirmed it says so.

- **Quotation attribution by an LLM from a closed list of characters works, and beats the
  pipeline tools.** Llama-3-8B, zero-shot, on PDNC (the largest annotated corpus of quoted
  speech in novels), given the gold character list: 90.6% overall on PDNC1 against
  BookNLP+'s 78.5%; on quotes with no explicit speaker clause 89.1% against 68.9%
  (Michel et al. 2024, <https://arxiv.org/html/2406.11380v3>). The same paper names the
  failure without the list: the model "was often predicting aliases that were not in this
  list". **Adopted**: the speaker of each line is an enum of the refs present plus "you",
  "nobody" and the beat's own mention ids. A caveat they state themselves: they cannot rule
  out that the novels were in pretraining; our beats were not.
- **Restricting the candidates is what moved the pipeline tools too.** BookNLP's
  attribution went from 0.40 to 0.62 on PDNC when each quote's candidate mentions were
  restricted to spans that resolve to one character (Vishnubhotla et al. 2023,
  <https://arxiv.org/html/2307.03734>); explicit quotes 0.64 → 0.93, implicit 0.28 →
  0.47. **Adopted** in the same shape: the mentions the reader is asked about are found by
  code from the engine's own vocabulary, and each is answered from the closed list.
- **What the pipeline tools abandoned**: open-vocabulary speaker prediction (BookNLP-OG,
  the 0.40 above), superseded by candidate restriction; and the LLM paper's open-alias
  setting, which they report only as an upper bound because of the invented aliases.
  **Refused** accordingly: any free-text "who" anywhere in the schema.
- **Coreference as multiple choice.** Prompt-based coreference has been posed as
  multiple-choice over candidate antecedents (the MQA format, cited by Gan et al. 2025,
  <https://arxiv.org/pdf/2509.11466>, who report that untuned LLMs "underperform on
  coreference resolution"). I could not read the format comparison's numbers from the
  PDF, so no number is claimed here. **Adopted**: "same as mN" offers each mention only
  the EARLIER mentions — a closed choice the sampler enforces — instead of asking the model
  to cluster.
- **Extraction must be grounded in the source.** LangExtract (Google, 2025,
  <https://github.com/google/langextract>) maps every extraction to its character span and
  marks one it cannot locate with `char_interval = None`, advising callers to keep only the
  located ones; its examples insist on "exact text … no paraphrasing". The anchor-constrained
  KG paper (<https://www.mdpi.com/2073-431X/15/3/178>) reports fewer than 1% fabricated
  subjects or objects once every element had to trace back to a span. **Adopted**: every
  free string the reader returns (a newcomer's words, a place's name, a placed person) must
  be on the page — the narration for a newcomer, that speaker's own line for a place —
  or the answer is dropped with the reason logged. Nothing is "fuzzily" re-anchored.
- **Constrained decoding covers few schema features, and llama.cpp fewest.**
  JSONSchemaBench (Geng et al. 2025, <https://openreview.net/pdf?id=FKOaJqKoio>) counts
  schema features each engine enforces; a summary of it reports llama.cpp's coverage
  falling to 39% on the hardest set (I read that figure in the summary, not in the paper).
  **Adopted**: every construct used was probed on this stack first (below),
  and the schema uses nothing else — no `contains`, no `prefixItems`, no conditionals.
- **Precision over recall when the page is unclear** — Muzny et al. 2017's sieve, already
  cited in `judgement.doubt_tags`, left a third of quotes unattributed for 90.4%
  precision. **Adopted**: "nobody" is always a choice, and a failed check drops the
  answer rather than guessing.
- **Could not source**: any published measurement of LLM *people/newcomer* detection in
  generated game prose ("is this a new person, or a description of one already here?");
  any study of a 0.6B extraction model on narrative coreference; anything published by
  AI Dungeon, Hidden Door, Inworld or Aventuras about how (or whether) they extract
  characters and places from their own generations — Aventuras' README says world state
  "is tracked turn by turn" and does not say how.

## The schema, and what the sampler enforces

Probed 2026-10-03 on gemma-4-12B heretic (Ollama), 6 runs each, every prompt asking for
something the schema forbids (`scratchpad/br/probe.py`; the numbers are copied here):

| construct | held |
|---|---|
| object of objects, each with two required enum properties | 6/6 |
| a different enum per property (m2 may say "same as m1", m1 may not) | 6/6 |
| array of objects, `maxItems: 2`, asked for five | 6/6 |
| enum inside array items | 6/6 |
| empty array allowed | 6/6 |

One more measured in passing: the enum held "kind" to the vocabulary, but the model then
chose a wrong member ("the forge" as a mill) when the right one was offered — an enum
guarantees the vocabulary, not the reading. That is what the bench measures.

## What retired, and what answers instead

Every function below read English in code to decide a fact about the beat. Each is gone
from the live path; the test that pinned it was moved to the reader's answer (a stubbed
reply, `tests/beat_reader/stub.py`) with its measurement docstring kept.

| retired | what it read | answered now by |
|---|---|---|
| `judgement.record_people`'s seen/heard reading: `seen_in_beat`, `_shown_in`, `_cue`, `_HEARSAY`, `_SEEN_HERE`, `_LOOKED_AT`, `_OBJECT_OF`, `_gendered`, `_said_to_live`, `_shown_again` | whether a phrase's person is shown here, only spoken of, or neither | the people call's newcomers: "here" / "elsewhere", with the page's own words (`play/aftermath/seen_people.py`) |
| `judgement.only_a_predicate` | "He is a large man" as a description, not a person | the mention answered with the ref it describes |
| `play/aftermath/speaker_real.py`'s `_from_tags`, `_from_the_page`, `_Room`, `_whose`, `_speaker`, `_clause` use | who said an untagged line: clause, carry-on, nearest person, pronoun gender | the people call's `by` for each line (`speaker_real.py`, rewritten) |
| `judgement.doubt_tags` | a tag the page contradicts, by `pc_spoken` and a speaker head noun | `beat_reader.reconcile_tags`: the reader's speaker against the tag |
| `judgement.hailed_by`'s untagged half | who hailed the player in an untagged line, by name words and role words | every line is booked first; `hailed_by` reads booked lines only |
| `judgement.apply_introductions`, `narration.named_in_apposition` (deleted) | a name given in speech or in apposition, and whose it is | the people call's `names`, checked by `beat_reader.name_refusal` (`seen_people.name_them`) |
| `rules/heard_places.heard_in`, `_phrases`, `_whose`, `_TIE`, `_HERE`, `_SOMEBODYS`, `_place_at` | places in a line, their landmark, a person's house | the places call's `places` (`play/aftermath/places_heard.py`) |
| `play/aftermath/mentioned_elsewhere.py`'s `phrases_at`, `_PRONOUN_AT`, `_place_at`, `_person_words` | "<person> in/at/near <place>", and "She's in the market" | the places call's `people` (`mentioned_elsewhere.py`, rewritten) |
| `play/aftermath/pronouns_adopted.py`'s `_from_mentions`, `_from_tags`, `_ATTRIBUTING`, `_LEADING` | a gendered noun or "he says" beside a they/them person's line | the people call's `pronoun cN` answers |

**Kept, because they check structure rather than read English:** `mentions.find` (marks
CANDIDATE spans from the engine's own vocabularies; the reader decides what each is, and
"nobody" is an answer); `speech.spans` (quotation marks); `name_given` (the exact name the
brief handed over, found on the page); `heard_places.record`/`of_here`; `population.note`,
`heard_of_match` and `find`; `judgement.embody_seen`'s limits (fight, cap, householder,
known person walked in). `note_cast` still books the brief's ledger; who is new and who is
here no longer comes from it.

## Measured: the bench

`tools/beat_reader_bench.py` over `tests/beat_reader/gold.py`: 52 hand-labelled beats —
25 from the owner's two 2026-10-03 saves (short excerpts), 7 from the Bobby corpus (read
from disk, never committed), 11 from the committed narrator-audit recordings, 3 of Sam's
2026-10-01 replay cases, the 5 name shapes the retired name patterns were tested on, and
one synthetic sergeant giving his name. gemma-4-12B heretic
(Ollama, temperature 0); the regex column is the harvesters as they stood at fceeb44, on
the same beats and the same scenes. Other sessions were using the same Ollama throughout
(lanes F and V), so the timings carry their contention: the same configuration measured
5.7 s median in one run and 3.5 s in the next.

| question | regex (before) | beat reader, final (2 runs) | one call (1 run) | Osmosis-Structure-0.6B |
|---|---|---|---|---|
| whole beat right (strict) | 22 / 52 | 45 / 52 per run | 33 / 52 | 4 / 44 |
| who each mention is (ref or nobody) | 75 / 76 | 150 / 154 | 75 / 77 | 34 / 71 |
| who each mention is (all, newcomers too) | 87 / 99 | 204 / 208 | 101 / 104 | 45 / 93 |
| bodies made: right / made | 6 / 17 | 20 / 23 | 10 / 11 | 4 / 14 |
| bodies wanted: found | 4 / 9 | 18 / 18 | 8 / 9 | 4 / 8 |
| who speaks each line | 80 / 109 | 216 / 218 | 107 / 109 | 55 / 105 |
| places the town lacks: found | 2 / 5 | 8 / 10 | 5 / 5 | 1 / 5 |
| places: wrong + duplicate | 1 + 1 | 2 + 0 | 11 + 1 | 6 + 0 |
| place kind right | 1 / 2 | 6 / 6 | 4 / 4 | 0 / 1 |
| place landmark right | 2 / 3 | 4 / 6 | 4 / 5 | 0 / 1 |
| people placed: found, wrong | 2 / 2, 0 | 4 / 4, 2 | 2 / 2, 3 | 0 / 2, 5 |
| pronouns settled right | 19 / 24 | 47 / 48 | 20 / 24 | 8 / 24 |
| names taken right, wrong | 2 / 5, 1 | 10 / 10, 0 | 5 / 5, 0 | 0 / 1, 0 |
| seconds per beat, median / max | 0.51 / 3.87 (one label call) | 3.54 / 13.59 | 6.08 / 18.32 | 9.82 / 30.58 |
| failed calls | 0 | 0 of 104 reads | 0 of 52 | 0 of 44 |

The regex column's "who" is the old labeller, which could only answer refs and nobody;
its bodies and speakers are the harvesters'. The beats the harvesters failed are the
day's defects: "He is a large man" (a second smith), the quoted player line made a person,
the merchant who moved on given a body, the man on the stool's lines booked to the
servant, the clerk's own keeper recorded as a stranger, the forge as two places.

**Decisions taken on these numbers:**

- **Two calls, not one.** One call answering everything scored 33 beats strict against
  45, and listed 11 wrong places against 2: asked for people and places at once, it
  listed the quay and "the turn for the wharf" as places. CLAUDE.md's "a model asked for N
  things answers in parallel", measured.
- **The places call lists only what the town lacks** (`LIST_TOWN_PLACES = False`). Asked
  to list every place including the town's own (code sorting them), it scored the same
  strict (42 against 42.5 a run) with twice the wrong places and two duplicates.
- **The kind is the model's own word, mapped by the engine's table** (`_kind_of`,
  `places.KIND_WORDS`). As an enum it scored 1 kind of 3: constrained decoding forced
  "tunnels" to "tannery" and "the main thoroughfare" to "theatre", sharing first letters.
- **"also called", not "same as entry N".** The link choice was never taken (the forge and
  the smithy came back unlinked twice at temperature 0); the other name in the same
  entry is.
- **The reader is shown the people known elsewhere in town**, after the first run made 6
  bodies of 14 out of people the engine already held (the merchant and the man left at the
  docks, the clerk behind the shut door).
- **Osmosis-Structure-0.6B is not the reader.** On the first full run (44 beats, the same
  prompts but before the last three changes above) it was strict on 4, read who a mention
  is right 45 of 93 and who speaks a line 55 of 105, and was slower than gemma (median
  9.8 s), because it is a second model to keep loaded beside the 12B. A rerun on the final
  configuration could not be made: with the other lanes' calls keeping gemma busy, Ollama
  left a request to Osmosis waiting for five minutes without loading it, twice.

**Remaining misses, by kind** (final run, both runs): "the merchant with a heavy pack …
walks a pace beside you … and moves on" still made a body (the reader says here); "The
man is a Korvu" once given to the figure c5; "the wharf" listed as a place (it is the
docks'); "Korgath Varn" placed somewhere by a line that names no town place; "the man at
the bar, a sturdy woman" (self-contradicting prose) answered nobody.

**Failure rate.** 0 failed calls in 364 bench reads (about 650 calls) across the four
gemma configurations, and 0 in the live turns below. When a call does fail nothing reads
the beat in its place: no newcomer, no booked line, no place, and a `beat-unread` row per
step (tests/test_beat_reader.py pins it).

## Measured: in the running game

Two turns through `/api/say` on a copy of the owner's live-data2 save (a throwaway data
root; the real %LOCALAPPDATA% untouched), gemma-4-12B: asked where to sharpen a rapier, the
man in the heavy coat answered with "a smithy … Or … The Forge"; the reader booked both
lines to c4 (the prose call had tagged neither), recorded both places with his own spot as
landmark, made nobody, and opened the conversation with him. 6.7 s and 4.0 s for the two
reads. The second turn's prose arrived with a broken `<say who=man in the heavy coat
to=you,"…` tag on the page — a prose-call fault the lifter does not catch, and not this
lane's; it is recorded for the narrator's owner.
