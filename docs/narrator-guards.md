# The narrator's guards

*Design record, 2026-09-17. Prior art first, then what was measured here, then the
decisions and what was refused. The code is `gm/narration.py`, `gm/agent.py`,
`gm/prompts.py`, `rules/cards.py`; the measurement is `tools/narrator_audit.py`; the
tests are `tests/test_narrator_guards.py`. `docs/narrator-reliability.md` is the running
measurement record this extends.*

## The request

> "make our narrator the best it can possibly be. look things up and figure out what you
> can do to make it better, push it to describe things in detail rather than to describe
> them as just 'they are unmade' which is a phrase used almost every single time I 1 punch
> an enemy. I do not want to continually run into narrator issue again and again."

And then: "I want the narrator to be bullet proof. It should [be] relevant and block
impossibilities, not get lost, incorporate hooks and quests and finally it should read
great doing it."

Five properties. Two of them — relevance and blocking impossibilities — are mostly the
work already recorded in `narrator-reliability.md` and the 0.1.9 detectors
(`contradicts-the-engine`, `ignores-the-dead`, the claim scrubber, the dead who stay
dead). This record is about the other three and about the one phrase the player quoted,
because the phrase turned out to be ours.

## What was measured before anything was designed

**The phrase is a template, not a tic.** `narration.press_the_death` appends an authored
sentence whenever the engine killed somebody and the prose did not say so. Its top rung,
for a death margin at or past the victim's whole hit-point maximum, read:

    The blow does not so much fell {name} as unmake {obj} — it carries through, and
    what folds to the ground is a ruin, dead before it lands.

A one-punch kill is exactly the case that reaches that rung. Read out of the player's own
saves: `spooter.json`, eleven beats, four kills, **four byte-identical sentences** — and
with the actor named `sailor`, "fell sailor as unmake them", article and pronoun both
wrong. `dorito.json`, "fell man as unmake them". The rung below it is one sentence too;
the rung below that, one sentence. A player who kills in one blow reads the same line
every time because the code has exactly one line to give.

**Why the template fires on nearly every kill.** The model writes a wounded man — "his
eyes widen as he struggles for breath" — because wounded men are what its training saw.
`cut_dead_men_walking` then deletes every sentence in which the freshly dead do anything
outside `_DEAD_MAY` (lies, body, blood, crumpled, …). A perfectly good killing sentence —
"the sailor crumples to the deck and does not move" — carries none of those words and is
cut as a dead man acting. Nothing about the death survives, `press_the_death` finds no
death language, and the template lands. It lands *after* grooming, so `review` never sees
it, and it is then in the beat the next turn's prose call is shown as "what you narrated
just before this". The raw model replies for those four turns were not logged (a
`resolution` entry carries no attempts), so the cut is demonstrated by
`test_narrator_guards.py` rather than forensics; the four identical shipped sentences are
the forensics.

**The second authored line, doing the same thing.** A sixty-turn baseline of the shipped
narrator (gemma-4 12B, `--script long`, 2026-09-17) came back 58/60 clean with openings
at 7% — the `formulaic-opening` repair holds. But counting four-word phrases *across*
beats, which nothing did:

| phrase | beats of 53 |
|---|---|
| the transition from the | **12** |
| to your left the / to your right the | 9 / 5 |
| the silence of the | 7 |
| the weight of the | 6 |
| the ground beneath your boots | 6 |
| he says his voice | 6 |
| the air here is | 5 |
| through it all you keep your attention where you put it | **4** |

The last row is `keep_the_thread`'s anchor sentence, verbatim, four times. It also caused
one of the run's two faults: `_THREAD_VERBS` treats "ask" as an engagement and captures
whatever follows it, so "I ask who I should speak to about work outside the walls" made
*who I should speak to about work outside the walls* the standing subject, and the anchor
carried the player's "I" into the narration as `narrator-in-first-person`.

Every one of those phrases is invisible to the current checks. `formulaic-opening` reads
the first two words of a turn; `repeats-an-earlier-beat` wants a whole sentence repeated;
`echoes-the-examples` indexes the worked examples and never the campaign's own prose.

**The sampler is not helping and could not.** `client.chat` sends `temperature`,
`num_predict` and `num_ctx` and nothing else. Ollama's `DefaultOptions()` sets
`RepeatPenalty` to **1.0 — off** — and `RepeatLastN` to 64 tokens, a window that cannot
reach the previous turn.

## What the traditions did

Two sweeps (repetition and samplers; grounding, salience and quests), each followed by a
critic pass against primary sources. Condensed here with what the critics corrected;
the sweeps' full notes are not in the repo.

### The mechanism has a name

Xu et al., *Learning to Break the Loop* (NeurIPS 2022, arXiv 2206.02369): sentence-level
repetition **self-reinforces** — the more times a sentence appears in the context, the
higher the probability of generating it again, and sentences that were most probable to
begin with reinforce fastest. That is the 16% → 26% → 48% curve `narrator-reliability.md`
measured on openings, and it is why feeding an authored line back as "what you narrated
just before this" teaches the model to write it. Friends & Fables reached the same
conclusion shipping to paying players: "LLMs tend to repeat patterns. Franz sees his last
few messages as examples of how his next one should be" — and, of prompt-side fixes,
"Some of these tendencies cannot be instructed away." The author of the DRY sampler,
independently: "Prompting the model to avoid looping has little or no effect."

### Kill text: axes, not adjectives

Six codebases were read at source. None of them solved thin, repetitive kill text by
asking for variety; every one added **mechanical axes** and kept its pools tiny.

- **ROM 2.4** (`fight.c`) has the 21-rung verb ladder (scratch … MUTILATE … "do
  UNSPEAKABLE things to"), keyed like Diku, Merc and Circle on **absolute** damage, with
  `.` or `!` at 24 points. **QuickMUD**, a ROM fork, is the one that rewrote it as
  `dam_percent = 100 * dam / victim->max_hit` in 5% steps with the punctuation break at
  45% — the critic pass caught the sweep attributing that to stock ROM. Damage *as a
  share of the victim* is the design adopted here, and it is QuickMUD's.
- **CircleMUD** (`fight.c`, `lib/misc/messages`): a random pool is consulted **only for
  misses and death blows**; ordinary hits are one deterministic line. The death pool is at
  most four deep and every line is anatomical and specific to the attack type — "You punch
  $N's head with a blow that crushes $S skull!", "You hit $N with such force that $S neck
  snaps in two!"
- **SMAUG**: severity index folds in how hurt the target already was; three ladders by
  weapon class. **BasedMUD**: relative damage picks the verb, absolute damage the
  adjective, and one adjective ("heavy") appears only when a skill procs — a tell.
- **Discworld MUD** (`attack_messages.c`): attack subtype × severity × **body part**, with
  a per-weapon override; the wrestling ladder escalates *through anatomy* (grab → arm lock
  → neck → throw → slam head), so concreteness arrives with severity for free.
- **DCSS** (`melee-attack.cc::set_attack_verb`): all weak weapon hits say "hit"; the
  **defender's species supplies the image** before any pool is consulted (ogre → "dice
  like an onion"); pools four or five deep; punctuation grows with `log2(damage)`. Its
  tracker has our exact bug — "every other kill opens something like a pillowcase" — and
  the fix widened the pool *inside* the mechanical bucket with concrete similes; a
  candidate was removed because its text was generated rather than fixed.
- **NetHack**: no random pools in combat at all; variety by combinatorics (eleven body
  plans × nineteen parts). `exclam()` returns `?`, `.` or `!` by damage, and its comment
  *refuses* a `!!` tier because the function's one integer carries no information about
  hand, weapon or wand — a distinction is dropped rather than faked.
- **Dwarf Fortress** (wiki lore, not primary): the 40d wound page carries a table of
  complete sentences by damage type × severity ("It is pierced!" / "It is badly pierced!"
  / "It is mangled!"); 0.31.01 (April 2010) replaced per-part hit points with layered
  tissue wounds, and the only composed message the critic could find quoted is a
  talk-page paste. Whether the table was *removed* is an inference from the systems
  change. What is primary is Toady's own bug list for the new system, which is entirely
  about *which events to report and how to compress them* — never about phrasing.

Five of these independently use terminal punctuation as a severity channel. The Diku
family emits the resulting state as a separate sentence from the blow.

**Never twice running.** Inform 7 (*Writing with Inform* §5.7) offers nine ways to pick a
random alternative and no default — omitting the choice is a compile error, which the
manual does not say but the compiler does (`PM_ComplicatedSayStructure3`) — and the
short-named one, `[at random]`, is "chosen at random except that the same choice cannot
come up twice running … to avoid the deadening effect of repeating the exact same
message"; the runtime rejection-samples. The Recipe Book ranks random pools as the floor
("apt rather than random"), and *Curare* keeps least-recently-used selection as a
turn-stamp on the *subject*. TADS 3 adds the warning that two alternatives alternate
visibly (ABAB) and that "the very lack of repetition in shuffled mode is sometimes
discernible as a pattern".

### What the sampler can and cannot do here

Read from Ollama's Go source, not its docs (the docs disagree with each other):
`api/types.go` exposes `temperature, top_k, top_p, min_p, repeat_penalty, repeat_last_n,
presence_penalty, frequency_penalty, seed, stop, num_predict, num_ctx` (and a deprecated
`typical_p`). **No DRY, no XTC, no `logit_bias`, no mirostat** — the request to expose
DRY/XTC (ollama#7504) has been open since 2024 with no maintainer response — and
`Options.FromMap` **silently drops unknown keys** with HTTP 200 and a server-log warning,
so an experiment with any of them would appear to work. `repeat_last_n: -1` is documented
as "the whole window" and is rejected or clamped to zero by current llama.cpp; test it
against the bundled build before trusting it.

The penalties that *are* exposed have a documented failure mode from llama.cpp's own
tracker: the most frequent tokens in prose are "spaces, punctuation, and words like `a`,
`the`" and in dialogue the speakers' names, so "we are penalizing the very structure of
standard English" (PR #5561, never merged); the patch flag `--no-penalize-nl` has since
been removed. Phrase-level banning that works — AntiSlop (ICLR 2026 poster), KoboldCpp's
`banned_strings`, ExLlamaV2 — backtracks and resamples, which costs 69–96% of throughput
at banlists of a thousand phrases and up; its API form needs `top_logprobs` on a
completions endpoint (not raw logits — a critic correction), which Ollama does now
expose, untested here. SillyTavern refused it as out of scope; AI Dungeon shipped token
banning and **deprecated it** because banning "car" also suppressed "cartoon", "carry"
and "scar".

What Ollama does give us: `format` as a real grammar (already used), `stop` matched on
decoded text, `logprobs`, and a hardcoded `cache_prompt` so a second candidate shares
the prompt pass.

### Metrics that measure the right thing

Holtzman's *Repetition* metric counts a phrase repeating three times **at the end of one
generation** — it scores our problem at zero. distinct-n is biased by length (*Rethinking
and Refining the Distinct Metric*, ACL 2022). The two that fit: the **self-repetition
score** (Salkar et al., AACL 2022) — n-grams of four or more words appearing in *multiple
outputs of the same system* — and the **gzip compression ratio** (Shaib et al., 2024),
original size over compressed so that *higher* means more redundant, which they find
"highly to moderately" correlated with the n-gram measures at a fraction of the cost and
insist on reporting beside length. Both are a few lines with no dependency.

### Salience, for hooks and quests

- **Valve's rule databases** (Ruskin, GDC 2012, confirmed against the slides' speaker
  notes): the query is a flat dictionary of facts; a rule is criteria that must all hold;
  the score is "the number of criteria in a rule … the simplest one imaginable"; ties are
  random; responses **write facts back** ("this line has been played", "speaking for the
  next few seconds" with an expiry) — that is the cooldown; and follow-ups are re-queried
  when they fire, so a line whose criteria stopped holding "self-terminates … You don't
  need any kind of explicit interruption mechanism." His regret: response-level cooldowns
  produced rules that matched with nothing to say; he wanted the rule to remove itself.
- **Emily Short** (*Beyond Branching*, 2016): salience-based selection picks the element
  "judged to be most applicable", ties random, and lets an author "build a rudimentary set
  of content with sensible, broad defaults, and then gradually add new, more salient
  content". Her warning, and Kreminski & Wardrip-Fruin's (ICIDS 2018): salience sequences
  *dialogue and colour* well; used to sequence *plot* (King of Chicago) it has "an obvious
  design vulnerability". The plot arc lives elsewhere.
- **Failbetter** (2011): one quality used for two meanings caused "problems of consistency
  and exploitation" — the one-vocabulary law, learned by somebody else.
- **Drama Llama** (2025) let an LLM judge storylet preconditions with a YES/NO prompt; a
  participating author reported trigger detection "did not work as expected", and the
  paper's own future work is cooldowns and fallback triggers — the deterministic devices
  the older traditions had from the start. **Do not ask the model whether a hook is
  salient. Compute it.**
- Booth's L4D Director (GDC 2009): "adjusts pacing, not difficulty" — a single intensity
  value with event-driven rises and a Relax floor. Its constants are a shooter's; the
  shape (a quest that has gone quiet gains urgency) transfers.

### Scene state is derived, not remembered

Inform 7's scenes begin and end on world conditions between turns (WI §10.9: the design
guards against "a character killed during Act I reappear[ing] unharmed in Act II", though
Inform frames it as a style it encourages rather than a mechanical guarantee); a room's
description is assembled from object state at LOOK time (RB §3.1). CircleMUD's
`make_corpse()` puts "The corpse of %s is lying here." *in the room as an object* with a
decay timer; DCSS marks blood per floor cell. Nobody in any tradition kept free prose as
the source of truth for what a place looks like now. The 2026 neuro-symbolic papers do
the LLM version — the symbolic model executes, the LLM narrates "without making up
details not included in the world state" — with a token cost of 3–13× per story
(ConWriter), which is why this record keeps the checks mechanical.

**Placement.** *Lost in the Middle* (Liu et al., 2023) measured GPT-3.5 on twenty
passages: 75.8% with the answer first, 53.8% in the middle, 63.2% last, against 56.1%
closed-book — the middle scored *below no context at all*. Critic caveat: that is a 4k
prompt on a hosted model, not an 8B local one at 16k, and a 2025 RAG study found
reordering no better than shuffling. Every shipped narrator nonetheless puts its
load-bearing note at the end (AI Dungeon's Author's Note "immediately before the most
recent AI response"; SillyTavern: "the closer … to the bottom of the prompt, the more
impact it has"). Cheap to honour, so honoured, and measured.

### What the critics corrected

- DECODE's "contradictions 29% → 1.1%" is the detector grading its own re-ranked output;
  human judges saw 31.8% → 25.6%. An NLI second opinion buys a modest relative gain, not
  a guarantee.
- *Lost in the Middle*'s "position 19" is the *last* slot of twenty, and the numbers are
  GPT-3.5's, not an 8B model's.
- Drama Llama's "did not work as expected" is one participant of six, not the authors.
- Booth's intensity is "a value" acted on as the max across four players; "float" was a
  gloss. Inform's "checked only between turns" was a paraphrase.
- HHEM-2.1-open being English-only is metadata plus inference.
- From the repetition sweep's critic pass: the percent-of-max-HP bucket is QuickMUD's,
  not ROM's (corrected above and in the code comments); AntiSlop's API sampler needs
  `top_logprobs`, not raw logits; Xu et al.'s ">90%" is >90% of *tokens* on constructed
  repetitions with a 16-layer Wikitext model — the direction transfers, the number does
  not; Shaib's correlation is "highly to moderately", and the ratio's direction is
  original/compressed; the Dwarf Fortress removal is wiki lore; Ollama's `typical_p` is
  in the struct but answered with HTTP 400; and the Inform compile error is the
  compiler's, not §5.7's.

### What the traditions abandoned

Dwarf Fortress's sentence table. The `penalty_threshold` patch and `--no-penalize-nl` in
llama.cpp. Mirostat and `tfs_z` in Ollama (removed), `typical_p` (deprecated). AntiSlop's
token matching, for string matching. AI Dungeon's token banning. Beam search for open
text. Valve's static and multi-variant scripted triggers ("Players learn all of them") and
its response-level cooldowns. Failbetter's overloaded qualities and count-down qualities.
Running summaries, three times over (SillyTavern's Smart Context, Friends & Fables'
memory summaries, Talemate's "it can get a bit messy"). Model-judged preconditions
(Drama Llama adding the deterministic devices back). Free prose as the record of scene
state: nobody kept it.

## Decisions

Every decision below keeps the shape CLAUDE.md records as the only one that has held:
**detect mechanically, repair with a targeted call, and put a deterministic backstop
under the repair.** Where a decision adds prose of our own, that prose is built from
mechanical axes and never repeats itself twice running.

**D1. A kill left off the page is a finding, not an appendix.** `press_the_death` stops
being a post-groom append and becomes `review`'s `death-left-off-the-page` (weight 3),
raised when the engine killed somebody this turn and no sentence about them carries
death language. The fix hint names the facts the engine holds — who died, the damage
type of the blow, how far past dead it went (as words, never a number), the origin
document if any, the actor's pronouns — and asks for two sentences specific to *this*
body and *this* blow. That is the targeted call. If the rewrite is refused or fails, the
authored line is the backstop, and it is rebuilt:

- keyed on **damage family × margin bucket** (CircleMUD's death pool, QuickMUD's
  share-of-the-victim), three lines per cell, each anatomical and concrete, and every
  one saying "dead" in as many words so the detector that judges the page recognises
  its own backstop;
- selected **least-recently-used per campaign** (Inform's `[at random]` made
  deterministic, Curare's stamp on the subject), so the same line cannot ship twice
  running and a long session walks the whole pool before any line returns;
- with the victim named properly — a bare common noun takes "the".

**D2. A fresh kill's own sentence survives.** `cut_dead_men_walking` is told who died
*this turn*; for them, a sentence carrying felling or death language (`_FELLED`,
`_DEATH_LANGUAGE`) is the killing blow and is kept. Long-dead actors keep the old rule —
"the stranger collapses" two turns after dying is the resurrection the cut exists for.

**D3. The narrator is measured against itself.** `narration.self_repetition` (four-word
phrases, content words, appearing in two or more beats; the hand-back and quoted speech
excluded) and `narration.compression_ratio` join the audit's texture and drift reports,
so the next sixty-turn run has a number to move. `review` gains `recurring-phrase`: a
four-word phrase of this turn that has appeared in three or more of the last twelve beats,
or a six-word phrase that appears in two or more of the last eight, named in the fix hint.
Calibrated against the baseline before it shipped: at "any of the last eight" the
six-word rule would have fired on 29 of 56 beats, most of them a beat honestly continuing
the scene of the one before it; at two of eight, 17 of 56, every one of them a tic —
"he says his voice", "the transition from the", "the silence of the", "hangs in the air".
Phrases that are mostly proper names are skipped ("the Guild of Salt and Timber"
recurring is the world, not a formula). No deterministic backstop — deleting a clause
mid-paragraph leaves a hole — so the retry is gated as every other rewrite-only finding
is.

**D4. Our own lines are never fed back as the model's.** A transcript beat records the
sentences the pipeline appended (`"added"`); the `earlier` beats handed to the prose call
strip them. Xu et al. is the reason: what the model is shown of its own past is what it
reinforces, and an authored anchor shown as "what you narrated" is a template being
taught.

**D5. The thread anchor stops being a formula and stops leaking.** "ask" alone no longer
sets a thread — the subject must read as somebody or something ("ask the smith", "ask
him"), not a clause, and any subject carrying first-person pronouns or a wh-word is
refused. The anchor is a small pool selected least-recently-used, and the subject inside
it is converted to the second person before it is placed.

**D6. The scene as it stands now, at the end of the prompt.** A short block derived from
engine state each turn — who lies dead here, who is hostile or afraid, whether a fight is
running or has just ended, the standing thread — placed *last* in the prose call's user
message, after the tells, where the shipped narrators put their author's note. Assembled
from state, never carried as prose (Inform; the corpse as an object). Measured by the
audit, not asserted.

**D7. One thread to pull, chosen in code.** Each turn every live card is scored by
criteria count in Ruskin's sense — pinned to this place; a person of the card present;
its keys in the scan window, the player's line or this turn's tells; an unticked quest
objective; and turns since the prose last *mentioned* it (a quest that has gone quiet
gains a point every few turns). The top card, and only the top card, is named at the end
of the prompt with its one most relevant fact or open objective. When the prose carries
the card's keys, the card's `mentioned` turn is written back (Ruskin's write-back; the
cooldown falls out of it). When a card has been urgent and unmentioned for long enough,
`review` raises `drops-the-thread` with the fact named — out of fights only, and with no
deterministic backstop, because an appended anchor would be D5's formula again. Secret
cards stay secret: the world's unwritten hooks reach the table through the watcher and
the plan, as they do today.

**D8. Concreteness is measured before it is enforced.** The Brysbaert norms score the
quoted phrase at 2.15 on a 1–5 scale against 4.2–4.6 for anatomical prose, and a
threshold near 3.5 separates every thin example from every concrete one in the sweep's
sample. But those norms are **CC BY-NC-ND**, which makes a shipped subset a derivative
work; the Glasgow Norms (5,553 words) and Lancaster Sensorimotor Norms (39,707) are CC BY
4.0, and neither is a drop-in (Lancaster's perceptual strength correlates with Brysbaert
concreteness at only r = 0.58). And concreteness is not specificity (Li & Nenkova 2015:
imageability was *higher* for general sentences). So: a concreteness report in the audit
first, from a CC BY resource, thresholds read off real output, and a finding only once
the number is shown to track what the player means by "thin".

## Refused, with reasons

- **Turning on `repeat_penalty` / `frequency_penalty`.** Documented to penalise English
  structure and speakers' names; the LZ-penalty paper measures both as ineffective; and
  the one setting that would let them see the previous turn (`repeat_last_n: -1`) is
  unreliable across llama.cpp builds. Revisit only with a measured run.
- **`stop` sequences as phrase tripwires.** A stop inside the narration string leaves the
  JSON grammar unterminated; the repair would start from a parse failure.
- **DRY, XTC, logit bias, AntiSlop backtracking.** Not exposed by Ollama, and unknown
  options are dropped silently. A backend swap (KoboldCpp has all of them) is a product
  decision this record does not make.
- **An NLI second opinion (HHEM, AlignScore).** Feasible on CPU, but transfers poorly
  out of its domain (DECODE), buys a modest human-judged gain, and is another 600 MB in
  a bundle that ships as one file. The mechanical checks stay primary.
- **Letting the model judge which hook is salient.** Drama Llama.
- **Telling the model to vary its language.** CLAUDE.md, Friends & Fables, the DRY
  author, and the 16% → 48% measurement all say the same thing.
- **Shipping the Brysbaert norms.** The licence.

## Measurement

Before: the 2026-09-17 sixty-turn baseline above, plus `spooter.json`'s four of four.
After: the same script, the same model, the same machine, one run at a time on the GPU,
reporting self-repetition and compression ratio by third alongside the existing columns;
and the kill-line pool walked in a unit harness, since a level-one fixture cannot be
relied on to kill in one blow. Numbers go in `narrator-reliability.md` when they exist.
