# Asking the GM

*Design record, 2026-09-18. The code is `play/gm_search.py` and `play/gm_answers.py`, the
prompt is `prompts.out_of_character_messages`, the tests are `tests/test_gm_questions.py`.*

## The request

> "make sure the /gm speaks naturally to the user. I am somewhat aware that in order for
> this to work semantic search may need to be incorporated because any system or place
> should be able to be asked about and an answer given. Just like if I was asking my GM in
> real life, I may be wrong about that though so don't just take my word for it."

## What `/gm` could do before

Three passes, cheapest first: the engine's own state by topic (who is here, hit points,
the pack, quests, the time); a rules entry whose NAME the question contained, matched
exactly or as a whole phrase (`_match`, deliberately never a loose contains — "reaction"
had once pulled the spell *Negative Reaction* out of a question about the crowd); a world
entity spelled exactly (`World.by_name`). Anything else went to the model with the scene
brief. So "what is this town's council?" found nothing — "this town" is not a name — and
the model answered from the brief's eight fact lines or from nowhere.

## What was measured first

Two probes against the shipped Aurvantis export (357 entities, 1.28 MB of typed facts and
prose; 16 factions; 49 events) and the rules catalogue (1,474 feats, 3,040 spells), using
SQLite's FTS5 — compiled into this Python (3.13.7, SQLite 3.50.4) and into the frozen
bundle, no dependency.

**Named things are found.** "who is Drenn Ironvale" ranks him first at a score of −22;
"what does the spell fireball do" ranks Fireball; "what does power attack do" ranks Power
Attack; "who is the most powerful person in Vormoor" ranks Vormoor and then its four
residents; "who are the Sootspars" ranks the family. One millisecond a query; the index
of the whole world builds in a tenth of a second.

**Two failures, both mechanical.** A question about *here* ("what is the tension in this
town about", "is there a temple here") has no name to match and lands on whatever shares a
preposition with it. And in one index the 4,500 rules entries drown the 500 world entries
on generic words: "what are the winged clans" returned five feats about wings; "where can
I buy rope" returned *Rope Trick*.

**The world has a floor.** Searched alone, a question the world has no words for scores
−1 to −3 against noise; a real match scores −6 to −23. That gap is a threshold the code
can refuse on.

## What the traditions did

A sweep with a critic pass behind it, which checked every number below against its
primary source and corrected five (noted where they bit). Condensed findings.

- **BM25 is the favourite, not the fallback, on this kind of corpus.** BEIR (Thakur et al.,
  NeurIPS 2021, Table 2, nDCG@10, zero-shot): dense retrievers trail BM25 on average — DPR
  by 47.7%, ANCE by 7.4%, TAS-B by 2.8% — and the paper's own summary is that "BM25 is a
  robust baseline and re-ranking and late-interaction based models on average achieve the
  best zero-shot performances, however, at high computational costs". Those are 2021
  models; none of the embedders one would ship today was in it. EntityQuestions
  (Sciavolino et al., EMNLP 2021, Table 1, top-20 accuracy), the closest analogue to a
  corpus of place and family names: DPR trained on NQ 49.7% against BM25 72.0% (DPR-multi
  56.7%); "dense retrievers can only generalize to common entities unless the question
  pattern is explicitly observed during training". pathfinder-rag (24k d20pfsrd pages,
  n=127 hand-checked queries, no held-out set) found equal-weight fusion of BM25 into its
  dense retriever a net negative and its author calls only "heavily down-weight BM25"
  defensible — a finding about a 24k-page corpus of near-duplicate sibling pages, not
  about a few hundred named entities. (rag-dnd-rules-lawyer's 0.30 full-text baseline
  was first cited here as evidence too; the critic pass found it measures an AND-joined
  Postgres tsquery that returned nothing for most multi-word questions — the trap
  `match_expression` is written to avoid, not a fact about BM25.)
- **The one thing dense retrieval buys is paraphrase** — "who runs it" against a fact typed
  *Formal Power*. The export's typed facts are a topic table in Inform's sense, and a small
  map from question to fact type closes that gap deterministically.
- **An embedding model is a second download.** Nothing on this machine's Ollama is an
  embedder; the usual choice (nomic-embed-text v1.5) is 274 MB and needs task prefixes
  (`search_document:` / `search_query:`) that Ollama does not add — the code would have
  to; the smallest (all-minilm, 46 MB) truncates at 256 word pieces. Every shipped LLM
  narrator that kept keyword activation (NovelAI, AI Dungeon) still has it; SillyTavern
  deprecated its ChromaDB "Smart Context" and its World Info docs still say "if you want
  deterministic and predictable results, stick to keyword matching".
- **The refusal must live in code.** FaithEval (ICLR 2025, Table 4, strict match): told to
  answer "unknown" when the context lacks the answer, Llama-3.1-8B-Instruct did so 37.6% of
  the time, gemma-2-9b-it 50.3%, GPT-4o 59.7%. (An earlier draft added that the
  instruction cost accuracy on answerable questions; the paper measured that only with its
  conflict-context instruction, on GPT-4o and Claude — struck.) pathfinder-rag: of 26
  questions where retrieval came up empty, 19 (73%) were answered confidently anyway.
  RAGTruth (Table 7, 450-instance test split): Llama-2-7B hallucinated in 51.8% of answers
  *with the passage present*, Mistral-7B in 57.6%, GPT-4 in 9.3%. Vectara's leaderboard
  puts gemma-3-12b at 4.4% on short summaries — but that figure moved from 2.8% when the
  scorer changed in November 2025, so it is an order of magnitude, not a number to design
  to.
- **Small models can copy but not cite.** ALCE (EMNLP 2023, Table 4, ASQA): LLaMA-2-Chat
  13B citation recall 38.4% (±5.9), ChatGPT 73.6%. The source label belongs on the
  passage, written by the code that found it.
- **Put the passages last.** Lost in the Middle.
- **The table's tradition.** A GM tells the player what the player asks, out of character
  (the Alexandrian's "default to yes"; GUMSHOE, which "makes the finding of clues all but
  automatic" because failed knowledge rolls stall play; Apocalypse World's "always say
  what honesty demands"). PF1e's Knowledge skill is a gradient for *character* knowledge —
  rulers, laws and popular locations at DC 10, rumours at 15, hidden organisations at 20,
  and "Retry? No" — and PF2e's Recall Knowledge lets the GM answer a critical failure
  falsely, coupled with a rule that after any failure further attempts are fruitless.
  `/gm` is the player asking, not the character; the world's record is told straight.

## Decisions

**G1. "Here" is the place the engine knows.** A question with deixis — here, this town,
the city, around here — is about the current location, and the GM's notes on it are the
whole entity: every typed fact (the brief carried eight), its prose, the places inside
it, who lives there and what they are, and the nation above it. `gm_search.dossier`
writes them, the fact the question is about first (`INTENTS`).

**G2. Names are found by BM25 over the world alone.** `gm_search.search`: FTS5 with porter
stemming, the name column weighted ten to one, quoted adjacent-word phrases and then quoted
tokens, OR-joined (raw text with an apostrophe or a question mark is a syntax error, and the
implicit AND between bare tokens is what made another project's full-text baseline return
nothing). The phrases are what lift a name made of ordinary words: "the Long Peace" scored
−3.9 on tokens — noise — and −7.8 with the phrase; every proper name roughly doubled; noise
did not move. Entities, factions and events; the rules stay with the existing name
matcher, which is precise and had a measured reason to be. Top three above the threshold,
one per name and kind, labelled in code with name, kind and where. A row whose whole name
the question contains goes first whatever BM25 said: for "tell me about the Kragmoor
Horde" three shorter rows about the nation outscored the nation itself by half a point,
and the one passage the player wanted was cut off. And the count is the code's: shown
three Sootspars, the model said the record "lists three individuals" of a dozen, so the
header now says how many matched.

**G3. Nothing filed is said by the code — when the code can be sure.** "Unknown" is
checked against the index itself: a word in no document of the world, not one that scored
low. Two shapes qualify (`gm_search.unfiled`): a proper name — a capitalised word that is
not the sentence's first — carrying such a word ("who is Grimble", "where is Hollin
Stair"); and a lowercase head phrase after "who/what is the", "about the", "called" whose
words the world has none of, none of them a word about the game itself ("what are the
winged clans" is refused; "any advice about the fight" is not, although this world's
1.28 MB never says "fight" or "advice"). The refusal carries the first lines of the notes
on where the party stands, so the player still gets something true. Everything else goes
to the model told to say when the notes do not cover it — a weaker guarantee, taken
knowingly, because the alternative is refusing questions the record could have answered.

**G4. The passages go last**, after the question, in the user message, with the
instruction to answer from them and say when they do not cover it. The scene brief
stays as the standing ground. The notes on the current place go along whenever the
question names nobody ("who guards the gate" found a town called Dustgate; the gate meant
was this one), and when the model is unreachable the record and the notes are printed as
they stand — the deterministic backstop.

**G5. The engine answers only what it is sure of.** Measured live before this shipped, ten
questions through `/api/say`: nine never reached the record, because `gm_answers` matched
its state topics on bare words ("who" in "who runs this town" gave the roster, "have" in
"how many hit points do I have" gave the pack) and its rulebook matcher accepted a
one-word prefix of a name ("temple" found the Temple Sword, "town" the Town Watcher,
"winged" the spell Winged Sword — each the only entry beginning with that word). The topics
are phrases now, and a one-word prefix finds a rules entry only when the question named the
catalogue ("the spell magic"). The world's exact-name finder, which answered "who is Drenn
Ironvale" with "Person" and stopped there, is gone; the record is the retrieval's.

The second live run (fifteen questions) found the last shape of it: "who guards the gate"
was answered with the bestiary's *Guards* — an exact one-word name match, on a verb. The
catalogues are full of ordinary words filed as names: 2,137 of 7,135 creatures are one
word (*guards*, *acolyte*, *merchant*, *wolf*), 380 spells (*light*, *fear*, *jump*, *sleep*,
*command*, *break*), feats (*run*, *dodge*), weapons (*club*, *net*). So a one-word exact
match counts only when the question has the shape of asking what a thing IS — "what is",
"what does … do", "how does … work", "explain", "tell me about" — or names the catalogue.
"Is there light here" and "should I run" are about the scene, and go to the GM.

**G6. The engine's refs never reach the player's eye.** The scene brief names people with
their refs ("the apprentice minding the door (c1)"), and the model, given a shorter handle,
used it: "the confrontation with c1". The answer is repaired in code from the scene's own
actors — every ref replaced with the name it stands for — rather than the model told not
to, because told-not-to is the fix that never held (CLAUDE.md).

**Refused.** Dense embeddings and a second model (above). Asking the model to cite
(above). Routing `/gm` through the character's Knowledge skill: the player asked out of
character, and a "your character does not know" answer to a question about the town
they are standing in would be the game refusing to be a GM. The gradient is real and is
noted for the day the *character* asks somebody in the fiction.

**Also refused.** Asking the model to cite (above). Routing `/gm` through the character's
Knowledge skill: the player asked out of character, and a "your character does not know"
answer to a question about the town they are standing in would be the game refusing to be
a GM. The gradient is real and is noted for the day the *character* asks somebody in the
fiction. Any Vectara percentage as a design constant (above). FTS5's presence in the
frozen app taken on trust: the bundle ships its own sqlite3 DLL, and the packaged build is
asked a `/gm` question before a release is cut.

## Measurement

The probes above, `tests/test_gm_questions.py` (the fixture world asked the same questions,
ranks and refusals pinned) and `tests/test_gm_answers_the_question.py` (the ten live
questions, none of which may match an engine topic or a one-word prefix again). Live
answers are read through `/api/say` in the running app before the change ships
(docs/narrator-reliability.md carries the record).
