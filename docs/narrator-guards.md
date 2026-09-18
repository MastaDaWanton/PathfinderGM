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

## The first run after, and what it corrected

Same script, model and machine as the baseline, run the evening the guards went in. It
reached turn 59 of 60 and died there — Ollama restarted under the running model — so
these are 58 turns, read off the campaign file rather than the audit's report. The
instrument is what the run improved most, and this section is the honest account.

**The narrator's own prose got better; the page got worse.** Self-repetition over the
narrator's beats fell from 0.131 to **0.098**, by thirds 0.104 / 0.120 / 0.077 →
0.057 / 0.083 / 0.071. Over the whole page it *rose*, 0.132 → 0.153, and the reason was
a third authored line: the watcher files its story award — "You gain 200 XP for moving a
matter along: …" — as a `setup` beat, so it was shown back to the model as "what you
narrated just before this", opened four of the last nineteen beats in that register, and
was the run's single most repeated phrase (seven beats, five of the top eight four-grams).
The same lesson as the death template and the anchor, arriving a third time: **every line
the pipeline puts on the page is a template, and the instrument has to tell the
narrator's prose from the engine's lines — while remembering the player reads both.**

**The phrase check was starved.** "the transition from the" held at 11 beats (12
before). Retrospectively, with its full window, `recurring-phrase` fires on 7 of 56
after-beats; live it fired once, because `earlier` was `transcript[-8:]` filtered to the
GM — four beats once the player's lines are taken out — against a check designed for
twelve. Every check that reads `earlier` had been working from that same four.

**One thread to pull pulled on every turn.** Fifty of fifty prose turns carried a pull,
fifteen distinct, one town-strain card eight times running; `note_mentions` stamped
fifteen cards as carried by a single beat about winged and flightless folk. Three
causes, all in the scoring: `keys_from` gives a shipped world card forty to
seventy-eight keys ("between", "power", "resources", "competition" are on most of them)
and one hit in three beats made a card "recent"; "pinned to this place" alone qualified
the town's strain card on every turn spent in town; and a card the beat had just carried
scored again next turn because the beat put its words in the window. The prose itself
was not harmed — none of the block's phrasing leaked ("nearest to hand", "still open",
"fraternal": zero hits) and the beats that took a card worked it in gracefully
("the crystalline sparkle of salt deposits — a sign of the long trade routes toward the
great refineries of Xylorvotha") — but `drops-the-thread` fired eight times, six on strain
cards, and the rewrites came back all but unchanged. The constants were also in the wrong
unit: `turn` counts transcript entries, two or three per turn of play, so "ten turns
quiet" was five.

**Two turns lost ten minutes each** to a fallback that never answered (D14, shipped the
same evening), and the run itself died to an unwrapped `RemoteDisconnected` — CPython's
`urlopen` raises it bare from `getresponse()` when the server drops a request already
sent, and `client.chat` caught `URLError` and `TimeoutError` only. A player would have
seen a 500 where the next line already writes "start Ollama".

The decisions that follow are the corrections.

**D9. The narrator is shown its own prose and only its own prose.** `narration.own_prose`
returns the last twelve `setup` beats, each stripped of what the pipeline appended; the
watcher's award is filed as `consequence` like every other engine line. Every consumer of
`earlier` slices its own tail, so the ones that wanted six or two see no change; the
phrase check sees its twelve.

**D10. Identity, not keys.** A card's identity is its title's content words, its open
objectives' words, the names of its people, and the proper nouns in its facts — not the
fact words. "Spoken" needs two of the card's keys or a person in the player's line or the
tells; "recent" needs two identity words or a person in the last three beats; a beat
carries a card when it names a person or two identity words. Measured on the run's own
beats, the loose rule marked up to nineteen cards carried by one beat; the strict one
marks the cards the beat is about.

**D11. The player's own matters, or nothing.** A quest, the errand the character came
with, a situation that arose in play, or a card whose person is standing here qualifies on
any criterion but time. The world's ambient cards — a town's strain, a guild's description
— qualify only when spoken of or recently in the prose; they are the brief's business
already. So a quiet town pulls nothing, which is most turns.

**D12. A matter the beat has carried rests until it has gone quiet.** Valve's "not if it
has been said in the last N", SillyTavern's Cooldown, Booth's relax phase. First cut as a
four-entry rest, which stopped the consecutive-turn repeats and was still too eager: the
second run (below) pulled the player's quest on thirty of sixty turns, the beat carried it
on five, and two of the five were forced. A card that has surfaced once is not pulled
again until twelve entries have passed since the beat last carried it; one that has never
surfaced is pulled until it does. Quiet is twelve entries and urgent twenty, stated in the
unit they are counted in.

**D13. The rewrite is for quests.** `drops-the-thread` is raised only for an urgent,
uncarried card of kind `quest`. A task the player took on and has not heard of for ten
turns is the failure the player described; a town's politics is colour the beat may pass
over.

**D14. A rescue that has not arrived in two minutes is not a rescue.** The primary prose
call keeps the generous timeout a cold load needs; the fallback gets 120 seconds.

**And the instrument.** `client.chat` wraps every socket-level failure as
`ModelUnavailable`. The audit survives a turn that raises (a `turn-failed` row, like any
other), stops after three consecutive turns that could not reach the model rather than
burning the script against a server that is not there, reports the narrator's own prose
apart from the page, and counts the pulls it sent.

## The second run, and what sixty turns can and cannot say

Same script, model and machine, with D9–D14 in. **All sixty turns completed, 59 clean**
(one `invented-name` that survived two repairs), no crash, no fallback stall, the six award
lines filed as engine lines, `recurring-phrase` fired seven times live and all seven
rewrites were accepted, four prose turns lost both models to the deflection detector and
shipped the engine's lines.

The repetition number did not move. Like for like — the narrator's own beats, the
engine's lines set aside in all three:

| | baseline | run 1 (58 turns) | run 2 |
|---|---|---|---|
| self-repetition | 0.121 | 0.098 | 0.133 |
| by thirds | 0.103 / 0.111 / 0.053 | 0.057 / 0.083 / 0.071 | 0.042 / 0.044 / 0.097 |
| split-half, same run | 0.054 / 0.047 | 0.049 / 0.051 | 0.036 / 0.062 |
| gzip ratio | 2.87 | 2.88 | 2.88 |
| commonest four-gram | "the transition from the" 12 | "the transition from the" 11 | three tied at 8 |

Three runs straddle the baseline and the two halves of one run differ by as much as two
runs do. **Sixty turns cannot resolve a difference of 0.03, and no claim about overall
repetition is made here.** What the runs do show is a distinction the design had not
drawn: the phrase check catches a *dense* tic — three of the last twelve beats — and
demonstrably rewrote seven of them, while the run's commonest phrases are *diffuse*, eight
of fifty-six beats, one in seven, which a three-in-twelve rule sees only when they cluster.
Lowering the threshold to two in twelve was calibrated against the baseline and fired on
nearly half its beats, most of them a scene honestly continuing. That is the DRY author's
warning arriving as a measurement: the model "can of course still repeat itself by
paraphrasing", and a detector on exact phrases has a floor. The mechanisms that would reach
below it are at the sampler (DRY, XTC), which Ollama does not expose, and prompt-side
requests for variety, which this record refuses on the evidence.

What did move is what the player quoted. The four-of-four death line, the four-of-fifty-three
anchor, the award line as narration: gone, and the tests hold them gone. The quest that the
model took up in this run was worked into eight of sixty beats — "the trail of the Sphinx
Whisker stretches out behind you", a guard repeating its name — and forced in two ("the
rhythmic chime of the Sphinx Whisker", a whisker that makes a sound), which is what D12's
longer rest is for; its effect is unmeasured until the next run.

## The morning after, at the table (2026-09-18)

The player played 0.1.9 and reported six things in two hours. Three were on the turn path
and belong in this record; the rest (an opening that fell to the template, the pregen
picker's world, the title bar, feat prerequisites) are in `narrator-reliability.md` and the
commits.

**D15. The deflection check that threw beats away.** `reintroduces_the_present` — "a
woman is there" of the one woman in the scene — had been rejecting BOTH models' prose on
role-noun actor names: four turns of sixty in the second audit, four of fourteen in the
player's save, every one a false positive ("a merchant guild house" on a wax seal, "a man"
in a market, "a stranger" in the woods), and what shipped instead was the engine's raw
lines: "You eats. You take stall." Three narrowings — only an introduction construction
counts; "another" is excluded; a common noun is a candidate only when the scene holds that
person as unique (sole other, or the thread's subject) — and the shape every fix here has
held under it: one retry naming who is present, then the next model, then the article made
definite and the beat shipped. The engine's tell verbs agree with "you" now, and "him what
he carries downstream" is no longer a thread's subject.

**D16. The world reacts.** Heat, the engine's note of what bystanders saw, was written
for a killing and nothing else; a sword through a merchant's crates carried nothing into
the next beat, and the crowd "remains silent". Heat has kinds now (killing, violence,
property, threat, delusion), from the outcomes or the player's line; the brief asks for
the reaction each deserves; `nobody-reacts` sends back a fresh beat in which nobody
present acts or speaks, with the people named. Rewrite-only and out of fights.

**D17. A claim about yourself plays as the boast it is.** "I reveal my true form as a
divine being" made the mud freeze to glass and put a stranger on his knees. Built first as
a door, like fiat; the player's correction — "it should read as my character being
delusional and the people should see it similarly" — is the design: the claim is caught by
SHAPE (asserting what one is, with a predicate naming a being, rank, lineage, calling or
power) and the SHEET decides whether it is true; a false one becomes a Bluff at the far
end of the ladder, the prose is told it is false and what each verdict looks like on the
faces around, `grants-a-nature` catches prose that makes it true with the granting
sentences cut and the world's answer written in from a pool, and heat of kind `delusion`
carries the crowd's verdict forward. Played live before it was committed: "the weary pity
of a man who has seen many people try to claim more than they are." The same run found
"I throw my coat open" starting a fight; thrown violence is *at* somebody now.

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
relied on to kill in one blow. The first after-run is the section above; the run with
D9–D14 in follows it. Numbers go in `narrator-reliability.md` as they exist.
