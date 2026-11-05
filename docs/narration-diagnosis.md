# Where the narration errors are born (2026-11-04)

The owner, 2026-11-04: "effectively nothing is finished this release I want to have better
narration. so lets make it work." The earlier benches (51 beats) could not separate
conditions. This one is large enough to, and it says where each error comes from.

- `tools/narration_diag/diagtrace.py` — instruments one process: every model call (who
  asked, the raw reply, Ollama's load time), every slot answer and why it was asked,
  every text change the pipeline made and by which function, the planned beat itself.
- `tools/narration_diag/drive.py` — plays turns in-process through the real view
  endpoints; the levers (slot temperature, best-of-N for act slots, the prose model) are
  applied by the wrappers in that process only. No default changed.
- `tools/narration_diag/blind.py` — blind sheets (conditions mixed and hidden), the rubric.
- `tools/narration_diag/attribute.py` — traces every scored error, in code, to its
  sentence, slot, writer and cause; errors a beat with bootstrap intervals; agreement.
- `tests/test_narration_diag.py` — the attribution's own cases.

Private saves, lines and prose stay in scratch. Nothing below quotes a page.

## The bench

44 lines from scratch copies of the two 2026-11-01 report saves and two fresh campaigns
(a fighter with a companion, a wizard), across: fights (melee declared and struck,
ranged, a trip, an ally, enemy turns), spells in a fight, theft seen and unseen, arrest,
trial, plea, the fine, the gallows walk, a commission and its price, crafting, trade and
two haggles, travel and arrivals, waits and sleep, questions, skill checks made and
failed, looting and harvest, a quest offered and taken, and five mature lines (a killing,
cruelty, a threat, crude speech, an intimate invitation that stops at the fade).

- **Baseline** (today's code, `igorls/gemma-4-12B-it-heretic`): 7 runs of every line,
  **308 turns**.
- **Levers**, runs 1-3 of every line, each turn played under all four back to back with
  the same Ollama seed per call: slot temperature 0.4, 0.1, best-of-3 for act slots
  (132 turns each, beside the 132 baseline turns of the same runs).
- **Model arm**: stock `gemma4:12b` (Apache 2.0) on the prose role, runs 1-3 (132 turns),
  as one block. The narrator role (interpreter, plan, enemies' turns) stayed on heretic so
  the engine reads the same line the same way; the readers and checks on the prose route
  (tells check, beat reader, read back) switched with it, as the app's own Settings would.
- Every turn: 2 blind scorers (agents, conditions hidden, items shuffled across conditions,
  44 items a sheet), the eight-code rubric of the earlier benches, Q (page quality), and new:
  R (refusal or breaking character), M (moralising), S (softened), a 1-5 prose rating, and
  a quote for every error so code can find it. 1,936 item-scorings in all. The model arm's
  sheets mixed the 132 stock turns with the 132 baseline turns of the same runs, scored
  afresh.

## Baseline: 0.20 errors a beat

| scorer | errors / beat (95% bootstrap) | beats with an error |
|---|---|---|
| A | 0.214 (0.162-0.269), 66 errors | 19% |
| B | 0.192 (0.143-0.247), 59 errors | 17% |

Agreement: same has-an-error verdict on 677 of 704 baseline and lever beats (kappa 0.88),
Pearson r 0.89 on counts, 88% of A's errors also marked by B (97% with the same code).
Re-scoring the 132 baseline turns of runs 1-3 in a fresh batch gave the same verdict on
121 and 126 of 132 beats (A, B); 0.186 against 0.205 the first time.

| activity | beats | errors / beat (95%) |
|---|---|---|
| loot and harvest | 14 | 0.68 (0.36-1.00) |
| skill check | 14 | 0.46 (0.29-0.64) |
| fight | 35 | 0.43 (0.27-0.61) |
| commission and craft | 21 | 0.36 (0.21-0.50) |
| theft | 14 | 0.21 (0.07-0.39) |
| mature | 35 | 0.17 (0.09-0.27) |
| arrest and trial | 49 | 0.16 (0.09-0.24) |
| quest | 14 | 0.14 (0.04-0.29) |
| wait and sleep | 28 | 0.12 (0.05-0.21) |
| spell | 14 | 0.11 (0.00-0.25) |
| conversation, trade, travel | 70 | 0.00 |

**The errors are systematic, not sampled.** Three lines carry 34% of them and seven carry
56%; the same lines err run after run.

## Where they are born

125 baseline errors over both scorers.

| writer | share |
|---|---|
| a slot's first answer (the model, in the plan) | 73% |
| an enemy-turn beat (free prose, outside the plan) | 11% |
| cut by a backstop (`cut_dead_men_walking` 9%, other cuts 1%) | 10% |
| the tells check's remake | 3% |
| the engine's own page line | 2% |
| a repair's own rewrite | 2% |

| slot | share |
|---|---|
| act slots (blow slots 8 of the 84 points) | 84% |
| enemy-turn beats | 11% |
| the doing slot, engine, tail | 5% |

Cause, by code (the quote's content words against the slot's ask, its tells and the shared
prompt): invention 49%, the slot's instruction stops short of a tell 14%, outside the plan
11%, written and then cut 10%, copied from the shared prompt 6%, the tell's own words
misapplied 5%, the doing slot shows the player's line as done 2%. The code cannot see a
paraphrase; read by hand, most "inventions" are the tell's wording misread (below).

The tells check flagged **none** of the 62 contradiction errors (E1/E2/E3/E4/E8) the slots
shipped; whatever it caught was remade before a scorer saw it. And best-of-3 changed the
pick on 17 of 188 act slots: the first candidate passes the check almost every time.

## The mechanisms (by hand, from the traces)

| # | mechanism | share | whose |
|---|---|---|---|
| 1 | One deed made two contradictory tells ("skin it and take its pelt": a harvest, then a refused take). The slot follows the refusal, or the tells check flags the right sentence against the refusal, the remake fails, the engine line stands in, and `cut_dead_men_walking` cuts it as the dead wolf acting, gluing two sentences | 14% | engine op, tells check, backstop |
| 2 | A declared fight: the act slot is told to show the squaring-up "and stop there", and the same tell's witnesses and warrant are never told | 14% | plan instruction |
| 3 | Enemy turns: free prose outside the plan writes a miss as a graze, a prone foe standing | 11% | the consequence narrator |
| 4 | "makes the check by 0" told as a failure (a trip "by 0" too) | 10% | engine tell wording |
| 5 | The player's line told as done beyond the tell: a dying foe "finished" by a blow that did not kill, a job taken with no tell | 9% | plan (the line rides the act slot; the doing slot shows it done) |
| 6 | A wait in minutes ("696 minutes pass") told as the wrong time of day | 6% | the tell gives no hour |
| 7 | Crafting placed at a bench the player is not at | 6% | the tell gives no place |
| 8 | A refused payment told as paid | 5% | the player's "and pay" in the slot |
| 9 | The sentence told as passed while the tell offers a last word first | 5% | tell wording |
| 10 | "it is still theirs" (ownership) told as never taken | 5% | tell wording |
| 11 | The escort's hold told as broken | 5% | the tell's options read as done |

## The levers

| condition | beats | errors / beat A (95%) | B (95%) | paired vs base, fewer/more (sign p) | prose rating | s / turn, median |
|---|---|---|---|---|---|---|
| base, runs 1-3 | 132 | 0.212 (0.136-0.295) | 0.197 (0.129-0.280) | — | 3.09 / 3.06 | 31.1 |
| slot temperature 0.4 | 132 | 0.303 (0.212-0.402) | 0.288 (0.205-0.379) | 7/20 (0.02), 7/20 (0.02) | 3.14 / 3.12 | 29.8 |
| slot temperature 0.1 | 132 | 0.212 (0.144-0.288) | 0.212 (0.144-0.288) | 12/14 (0.85), 12/15 (0.70) | 3.15 / 3.14 | 29.9 |
| best-of-3 act slots | 132 | 0.220 (0.136-0.303) | 0.242 (0.152-0.341) | 14/15 (1.0), 13/16 (0.71) | 3.17 / 3.10 | 34.0 |

**Sampling does not drive the errors.** 0.1 matched 0.8; 0.4 was worse on both scorers
(p = 0.02 uncorrected, three comparisons) with the excess spread over many lines, which
reads as noise more than a mechanism. Best-of-3 cannot help while the check it picks by
passes the first candidate. Not tried: a stock temperature arm, since no temperature won.

## Stock gemma4:12b

| | heretic (same runs, rescored) | stock |
|---|---|---|
| errors / beat, A (95%) | 0.182 (0.114-0.258) | 0.220 (0.136-0.303) |
| errors / beat, B (95%) | 0.189 (0.114-0.273) | 0.242 (0.159-0.326) |
| paired, stock fewer / more | | 11/15 (p 0.56), 10/16 (p 0.33) |
| refusals (R), moralising (M) | 1 (a tells-check remake out of character), 0 | 0, 0 |
| softened (S) | 2 (both the declared fight, mechanism 2) | 0-2 (the same) |
| prose rating | 3.14 / 3.12 | 3.11 / 3.08 |
| planned beats that fell back to free | 0 | 0 |
| s / turn, median (less Ollama's model loads) | 31.1 | 45.0 (31.4); loads 13.4 s a turn, first turn 27 s |

No difference the bench can see, and the same mechanisms in both (the skin chain, the
declared fight, enemy turns, the bench, the refused payment). Neither model refused,
moralised or softened a mature line. Stock costs two model swaps a turn while the
interpreter stays on heretic (6.5 s each, measured); one model for both roles would not.

## What to fix first (share of baseline errors)

1. **The declared fight's ask** (14%): tell the rest of the act's own tell after the
   squaring-up; the warrant is the engine's, not a blow. One instruction in `build_plan`.
2. **One deed, one tell** (14%): the redundant take beside a harvest (the shape of the
   2026-11-02 `acts_to_ops.table` fix). Then the two pipeline defects it exposed: the
   tells check reading a resolved act against a refused tell of the same thing, and
   `cut_dead_men_walking` cutting a sentence about working a corpse (and leaving
   "work.You").
3. **Enemy turns into the plan** (11%): the consequence narrator writes free prose with no
   tells check; the blow slot's facts already exist (`blow_facts`).
4. **Tell wording** (about 25% together): "by 0" as "just makes it"; the hour a wait
   ends at; where crafting happens; "still theirs" as ownership; the sentence not yet
   passed. Each is one string in the engine, read as written by every narrator.
5. **The player's line on the act slot** (9%, with the payment 5%): show only what the
   engine decided of it; the doing slot with no tell should not show the deed done.

Levers and a model swap: none moves the rate. The errors are in what the narrator is
told, not how it samples.

## Limits

- Scorers are two agents of one model family; their agreement may be partly shared bias.
- Engine outcomes are not identical across conditions: the same Ollama seed reaches the
  same call only while the turn makes the same calls, and the interpreter's reading and the
  dice then differ (a kill landed in one run and missed on a natural 1 in another).
- Fight turns list some tells twice (the turn and resolution rows); the scorers saw both.
- Cause-by-code is lexical; the mechanisms table is a reading of the traces by hand.

## The tells lane (2026-11-04, branch `fix/narration-tells`)

Mechanisms 1, 4, 6, 7, 9, 10 and 11, and three engine defects seen beside them. The rule
throughout: say each fact so a 12B narrator cannot read it the other way, and fix a
pipeline defect where code can see it (refs, roles, the reader's closed answers), never
with a regex reading English. Tests: `tests/test_tell_wording.py`, one per defect, plus
the pinned tells updated where they live.

| # | what the narrator was told | what it is told now |
|---|---|---|
| 1 | a harvest and, beside it, a refused take of the same pelt | one harvest (`acts_to_ops._take_is_the_harvest`: a take out of a carcass the sentence harvests, by ref) |
| 1 | a true harvest sentence flagged against the refused take; the engine line cut as the dead wolf acting; "work.You" | the tells check leaves a resolved act's slot alone against a refused tell about the same body (`Outcome.about`, `planned._same_deed`); `cut_dead_men_walking` spares the engine's own lines by a living actor and a sentence the player's character opens, and cuts from a sentence's first word |
| 4 | "makes the perception check by 0" | "makes the perception check, only just" (`dc.by`, every success template) |
| 6 | "696 minutes pass" | "11 hours 36 minutes pass: it is now early morning (about 6 in the morning), the next day" (`engine._hour_now`, the clock's own words); and a plan's extra `rest` beside a timed wait is dropped — "wait until morning" was slept twelve hours AND waited 696 minutes, out at 17:36 the next day |
| 7 | "… Finer work is done at the leather bench." | "X does the work right where X stands, at the market, not at the leather bench. … Finer work would be done at the leather bench." |
| 9 | "The sentence for murder is death … Before it is passed, X may speak once more" | "The guard will pass sentence after X's last word, and has not passed it yet: for murder the law's sentence will be death …" |
| 10 | "… who did not hand it over; it is still theirs." | "… who did not hand it over. X has it now; it still belongs to Y." |
| 11 | options inside the sentence of what happened ("A last chance: break their hold — slip it or wrench free — and run, or fight. Or go to it.") | the facts, then one closing sentence in one form for every tell that offers ways out: "Still for X to choose: slip their hold (Escape Artist) and run, wrench free of it (a combat manoeuvre) and run, fight, or go along." (`trial.choices`; the arrest, the questioning, the plea, the cell, the walk). Said in the future rather than as a bare negation: negated premises are a documented source of model hallucination (arXiv 2510.20375). A walk WITH the escort to the gallows is going along, no longer refused with the ways out listed |

Engine, seen in passing: a harvest of a body that still breathes is a coup de grâce first
(down and not dead, the engine's state; the harvest kept only where the sheet could take
parts); the plan's own blow at a body the table finished carries the table's
`coup_de_grace` (it stood in without it, so "finish off the dying bandit" was an ordinary
swing); out of a fight a coup de grâce walks up to the body first (it came back 422 at
15 ft once it was a coup de grâce); a blow at a body already down moves no attitude and
tells none ("cools: wants you gone").

### Measured

The bench's lines for these mechanisms — harvest and loot, the two climbs, the four
waits, the belt, the two thefts, the eight arrest, trial and gallows lines, and the
finishing blow (19 lines) — 3 runs each on this branch, paired with the same 19 lines'
runs 1-3 of the baseline (`res-wave2`, base). 114 turns shuffled into one blind set, two
scorers (agents), the same rubric (`blind.py`).

| scorer | baseline (57 beats) | after (57 beats) |
|---|---|---|
| A | 0.386 errors a beat (0.246-0.526), 35% of beats with an error | 0.105 (0.035-0.193), 11% |
| B | 0.351 (0.211-0.509), 30% | 0.123 (0.053-0.211), 12% |

- Same has-an-error verdict on 108 of 114 beats. Prose rating 3.16 → 3.39 (both scorers).
- By line, fewer/more errors after: A 8/2, B 7/3 (sign test p 0.11 and 0.34 — 19 lines
  is few; the beat-level intervals above do not overlap for A).
- Gone (errors A/B, before → after): the skin chain (5/5 → 1/1, the one left an
  omission of a sinew cut), "by 0" on the failed climb (3/3 → 0/0), the verdict told as
  passed (the theft plea 3/3 → 0/0, the murder denial 3/3 → 0/0), the belt at the leather
  bench (2/3 → 1/1, the one left an omission), the theft told as never taken (1/1 → 0/0),
  the wait until morning told as a night's healing sleep (2/0 → 0/0), the finishing blow
  (1/1 → 0/0), and the escort's hold told broken (gallows 1/1, gone; the gallows line's
  2/1 after are other shapes, below).
- What the scorers still found after (13 lines over both): omissions (a belt's assembly,
  a sinew cut, a sleep), a person or position added (a third arrester, "the gallows just
  outside the market", walking upstairs to drink), one hanging told "before the crowd can
  gather". None is a mechanism this lane worked on.
- **Seconds a turn: 31.9 → 51.9 median** — and it is contention, not the change: the same
  calls a turn (13.2 → 12.7), every call kind 1.5-2.3x slower (the interpreter's, whose
  prompt did not change, 5.4 s → 5.7 s; the slots 1.6 → 3.5 s), while the parallel lane
  benched on the same Ollama. An uncontended timing waits for the merged rerun.

Limits: the tells' new wording is visible on the sheets, so a scorer could tell the two
conditions apart by it (the condition itself was hidden); the finishing blow's three runs
were made after a fix found by the first three (the coup de grâce's walk), so its "after"
is the second try; and the scorers are one model family, as before.

## The plan's own patterns, fixed (2026-11-04, branch fix/narration-plan)

Four of the mechanisms above were in what the planned narrator's slots are asked. Each was
found by re-asking the slot's own recorded call (`trace.planned[].slots[].ask`) with one
thing changed, six to eight times, before any code moved; the counts are in the code's
comments and in `tests/test_planned_slot_shapes.py`.

| # | mechanism | re-asked before → after | the fix |
|---|---|---|---|
| 2 | declared fight "and stop there" | warrant told 0 of 4 → 8 of 8 | THE MOMENT: the squaring-up, then the act's own witnesses and warrant (`trial.report` carries each sentence as `told`), read back for any it left out (`planned._all_told`) |
| 3 | enemy turns as free prose | — | `planned.turn_plan`: one slot a blow, the turn block (whose turn, whom aimed at, unseen, a companion's manner), the page checks and the tells check, then the same groom tail (`GMAgent._groom_outcome`) |
| 5 | the line on a blow slot | dying bandit killed 6 of 6 → 0 of 6 | no line on blow slots; "could end it" and "rocks them" off the severity words, "grazes" off the close miss |
| 5 | the line on the player's own `say` | — | the say tells the words the engine heard, never the line |
| 8 | refused payment "as it happens" | paid 6 of 6 → 1 of 8 | a refused act is told as not happening, in the model's own words, without the line |
| 5 | act slot "doing it and what came of it" | clerk hands over supplies 2 of 8 → 0 of 8 | the engine's decision first, the line after it as how |
| 5 | tell-less doing slot "show exactly that" | job accepted 6 of 6 → 1 of 8 | asked as the attempt, nothing that comes of it |
| — | PEOPLE HERE / SCENE NOW called the dying "dead" | (with the two above) | dead by the engine's tag; the dying are "dying", the prone "on the ground" |

Not the plan's: **"makes the check by 0" (mechanism 4) is the tell's wording.** The climb's
recorded call came back failed 6 of 6; the same call with only "by 0" taken off the tell, 0
of 6; with "just makes", 0 of 6. Left to the tell-wording lane; on this lane's bench all 3
climb-fail runs still read as failed by hand (the scorers marked 1).

### The bench (paired by item and seed against the baseline, blind, two scorers)

Batch 1: 18 lines × reps 1-3 (the declared fights, the four fights with enemy turns, the
player's-line lines, the climb, and six control lines whose act slots changed shape), 54
turns beside the baseline's 54 of the same seeds, shuffled into one blind sheet set.

| | errors / beat, A (95%) | B (95%) | paired fewer/more (sign p) | rating A / B | Q pages A / B |
|---|---|---|---|---|---|
| baseline | 0.222 (0.111-0.352) | 0.259 (0.148-0.370) | | 3.04 / 3.02 | 8 / 9 |
| fixed | 0.111 (0.037-0.204) | 0.111 (0.037-0.204) | 8/3 (0.23), 9/1 (0.02) | 3.00 / 2.98 | 7 / 7 |

Agreement: kappa 0.71 on has-an-error, 14 of 18 of A's errors also B's.

Batch 2: the four enemy-turn lines × reps 4-7 (where the baseline's enemy-turn errors were)
and the two declared fights × reps 1-3 with the read-back added, 22 turns beside 22.

| | errors / beat, A (95%) | B (95%) | paired fewer/more (sign p) | rating A / B | Q pages A / B |
|---|---|---|---|---|---|
| baseline | 0.455 (0.182-0.727) | 0.409 (0.182-0.636) | | 3.05 / 2.86 | 7 / 7 |
| fixed | 0.136 (0.000-0.273) | 0.091 (0.000-0.227) | 8/2 (0.11), 7/1 (0.07) | 3.18 / 3.09 | 1 / 1 |

Agreement: kappa 0.94. Enemy-turn beats: 4 scored errors in the baseline's 16 turns (a wolf
"remains standing" after the trip, "the hand you use to pin it down", the garbled exert),
1 in the fixed 16 — written by the wrong-actor repair (`_repair_wrong_actor`, a whole-passage
rewrite inside the groom), not by a slot. The tells check remade 2 enemy slots across the 16
turns, one of them "graze your skin" written from no word of ours. Declared fights: the
warrant left out on 5 of 6 baseline beats, 0 of 6 fixed (the read-back fired once and the
remake told it).

What the fixed runs still got wrong: the declared fight's "Whatever you reach for does not
answer" (a repair's line, both conditions), a fine credited to the wrong person and an
escort's extra member (tell wording / a tells-check remake), three missiles for one
(the spell slot), and "Here is the payment" — words the interpreter put in the player's
own `say`, which the say slot now tells faithfully.

### What it costs

The enemy turn costs about one slot call per blow and one tells-check read where it was one
consequence call: on the batch-2 fight lines (Ollama shared with the parallel lane, but the
unchanged calls ran at the baseline's speed — the beat reader's median 0.91 s against 0.84)
the added calls came to about 6 s a turn, 2.7 s an enemy turn; wall median 70 → 86 s, calls
a turn 48.5 → 47.5. Batch 1's wall times are not usable: every call type, changed or not,
ran 1.5-2.6 times slower than the baseline's (the suite was running beside it and the other
lane was on the same Ollama). The declared read-back is one read a declared beat, two when
it fires.

## The follow-ups (2026-11-04, branch fix/narration-followups)

Three owner rulings of the day and five follow-ups the two lanes left. Tests:
`tests/test_narration_followups.py`, one per defect.

**1. A coup de grâce in a fight, by the book** (ruling). The reader's attack act carries a
closed `blow` (`interpret.BLOWS`: ordinary, finishing), glossed and demonstrated as `way` and
`until` were. Probed on heretic at 0.7, three asks a line: six finishing lines ("I finish him
off", "I slit the dying bandit's throat", "put the wolf out of its misery", "make sure the
thug on the floor never gets up" …) came back finishing 17 of 18 (the miss: "I drive my
dagger into the bound guard's heart", once); six ordinary lines ("I stab the bandit", "I kill
the guard", "I try to finish the fight quickly", "I hack at the ogre until it drops" …)
ordinary 18 of 18. `acts_to_ops.victims` makes a finishing blow at a body the engine holds
down or helpless the coup de grâce inside a fight too; any other blow there stays the
ordinary one at helpless AC; finishing words at a foe on their feet are an ordinary blow.
With a reading, the free door's regex (`judgement.declare_coup_de_grace`) stands down,
`inject_fight` no longer returns early on finishing words (that bail was the same regex
standing the reading down), and a coup de grâce the plan wrote at a body the reading struck
ordinarily in a fight is taken off it. The engine, in a fight: refused after a move this
round or a blow or spell already resolved in the batch (`Engine._coup_round_spent`); the
attacks of opportunity raised at the blow's point of commitment, only for a blow that will
land, from every foe threatening the attacker (`Engine._coup_provokes`, the shape of
`_leaving_the_fight`); told as "which takes the whole round"; and the round spent
(`Engine._coup_paid`: the move, and every blow of the attacker's still queued). Live,
through `/api/say` on the wolf fight with a dying wolf beside the player and a second at
their shoulder: read `attack, blow: finishing`; the second wolf's bite first (a miss); then
"delivers a coup de grâce, which takes the whole round: no roll to hit, and a critical hit
by right … fails the Fortitude save (7 against DC 20). The wolf is dead." Not built: a
declared move after the coup in the same turn (`_op_move` does not ask `move_spent`), the
two-round version against total concealment.

**2. Long waits do not heal** (ruling). Confirmed: a wait shorter than a lived day sleeps
nothing and heals nothing (nonlethal damage and fast healing still mend by the hour). A wait
of four hours or more with no night slept in it now tells "X stays awake the whole time and
does not sleep", and ", so no wound heals: only sleep does that" when the character is hurt
(`Engine._stayed_awake`).

**3. Working a body that still breathes** (ruling). As the tells lane built it; now tested
through the engine as well as the table: the coup de grâce, then the harvest of the dead.

**4. No whole-passage wrong-actor rewrite on a planned enemy turn.** Of the two options, the
slots' own tells check is the cleaner: `_groom(whole_rewrite=False)` with an actor runs the
detector and keeps what it saw as a turn-log note, and rewrites nothing. The case it came
from: a creature's `use_ability` arrived with no actor and was resolved as the PLAYER's
("[the player] has no ability called [a power]"), so "you" was the tell's true subject, the
detector fired on a true page, and the rewrite invented. That unowned `use_ability` is an
engine defect of its own and is not fixed here. On the bench below the detector fired on
none of 23 enemy turns in either condition, and the rerun of the run it came from (punch2,
run 7) took another path and did not reproduce the refusal; the test replays its shape.

**5. Enemy-turn remakes in the training log.** `GMAgent.last_turn_written` (the turn's own
plan, slots, brief and remakes), written by `play.views._log_turn_remakes` through
`corrections.log_auto` once the turn is on the page. No enemy slot was remade on the bench
below, so this is proved by the test, not live.

**6. End turn briefed.** `play.views._brief_the_npc_turns`: an agent with no brief gets the
player's turn's own `scene_brief` before the first creature acts (planned narration only).
Live: End turn pressed with nothing declared on the market fight, `/api/combat/act`, three
creature turns; every enemy plan opened "THE SCENE (reference; the only things that exist):"
followed by the world, the hour, the place and the places here, where it had been empty.

**7. "Here is the payment".** Not the reader's: the recorded run has the reading as `sell` +
`give`, no words said, and the `say` written by the PLANNER, passing `own_words_only` with 2
of its 3 content words the player's. With a reading that names no words said, a say is held
to the line's own words throughout. The line rerun three times with the plan lane's seeds:
the reading was the same each time; one plan's say ("I agree to your price.") stood, two
("Fine, I'll take it at that price.", "I accept your price.") were struck; no page told the
payment as made.

**8. "only just".** The climb's recorded call re-asked six times a wording at its own
temperature, read by hand: "by 0" failed 6 of 6, "just makes" made 6 of 6, ", only just"
made 6 of 6, narrowly. Kept (`dc.JUST_MADE`).

### The bench

The four enemy-turn lines (shoot, trip, punch2, magic missile), runs 4-6 on this branch,
paired by item and seed with the plan lane's fixed runs 4-6, 24 turns in one blind set, two
scorers (agents), the same rubric.

| | beats | errors / beat, A (95%) | B (95%) | enemy-turn errors | Q pages A / B | rating A / B |
|---|---|---|---|---|---|---|
| plan lane | 12 | 0.083 (0.000-0.250) | 0.083 (0.000-0.250) | 0 in 23 turns | 1 / 1 | 3.08 / 3.42 |
| follow-ups | 12 | 0.083 (0.000-0.250) | 0.083 (0.000-0.250) | 0 in 23 turns | 3 / 3 | 3.08 / 3.50 |

Agreement: kappa 1.00. The one error each side is the spell slot's three missiles for one.
The Q pages are the player's beats, not enemy turns: the declared shot told as a hit and then
still being readied (2 follow-ups, 1 plan lane) and one fragment; none is in code this branch
changed. Twelve beats a side cannot show a difference this small either way. Seconds a turn:
the medians (103 against 86) were taken with the full suite running beside the bench and
another live check on the same Ollama, and are not a measurement.

Seen in passing, not fixed: the death line `press_the_death` writes for a beast ("The wolf
staggers two steps, hands full of it, and sit down against nothing and are dead") is a
humanoid template with broken agreement.

## The rerun (2026-11-05): before and after the three lanes

The same 44 lines, the same snapshots, the default condition, 7 runs each (308 turns) on
689e7c73 (the tells lane, the plan lane and the follow-ups), each turn paired by item, run
and Ollama seed with the baseline. The bench driver needed one change: an enemy's turn is
now a planned beat of its own (`planned.write(acting=…)`), so a turn holds several beats
whose slots share keys; the trace records which beat each slot answer belongs to, and the
attribution names an enemy's slot as such (`fact1@the wolf#2`, "enemy turn: act").

Ollama was uncontended: `ollama ps` every two minutes through the run showed only the
heretic model loaded (54 readings), and model loads came to 85 s over 308 turns.

**One line no longer narrates.** "I swear I never touched her", at the trial, is refused
before the turn on all 7 runs ("saying so does not make it so" — the false-claim refusal,
`gm/means.py`), where the baseline played it all 7 times. The refusal code did not change;
the interpreter's prompt did (the follow-ups' new `blow` field and its demonstrations), and
it now reads the denial as a claim. That line is left out of both sides below (301 pairs).

Blind: the 301 baseline turns and the 301 fixed turns in one shuffle, conditions hidden, two
scorers (agents), the same rubric. The new tell wording makes the fixed side somewhat
recognisable ("only just", "stays awake the whole time"), which a scorer could notice.

| | baseline | fixed |
|---|---|---|
| errors / beat, scorer A (95% bootstrap) | 0.203 (0.153-0.256), 61 errors | 0.096 (0.063-0.133), 29 |
| errors / beat, scorer B | 0.179 (0.133-0.229), 54 | 0.080 (0.050-0.113), 24 |
| beats with an error, A / B | 55 / 47 of 301 | 27 / 23 of 301 |
| prose rating, A / B (1-5) | 3.10 / 3.08 | 3.06 / 3.09 |
| Q pages, A / B | 44 / 43 | 42 / 42 |
| S (softened), A / B | 2 / 0 | 4 / 6 |
| refusals, moralising | 0, 0 | 0, 0 |

**Paired.** By line (7 runs summed): fixed fewer on 20 of 43 lines, more on 7, tied 16
(sign test p = 0.019, scorer A); 18 / 7 / 18 (p = 0.043, B). By beat: fewer on 48, more on
19 (p = 0.0005, A); 42 / 16 (p = 0.0009, B). The difference a beat, with lines resampled:
-0.11 (95% -0.19 to -0.03, A), -0.10 (-0.19 to -0.02, B). **The errors halved, and the
drop holds by line, not only by beat.** The baseline side, scored afresh in this batch,
came out where it did the first time (0.191 against 0.203).

Agreement was lower than on the first bench: same verdict on 572 of 602 beats (kappa 0.77),
Pearson r 0.80 on counts, 73% of A's errors also marked by B. Both scorers' counts move the
same way by about the same amount, so both are reported rather than adjudicated.

| activity | beats | baseline errors / beat | fixed |
|---|---|---|---|
| loot and harvest | 14 | 0.64 | 0.21 |
| skill check | 14 | 0.43 | 0.07 |
| commission and craft | 21 | 0.31 | 0.19 |
| theft | 14 | 0.29 | 0.07 |
| fight | 35 | 0.27 | 0.09 |
| mature | 35 | 0.24 | 0.00 |
| wait and sleep | 28 | 0.16 | 0.04 |
| quest | 14 | 0.14 | 0.00 |
| arrest and trial | 42 | 0.11 | 0.15 |
| trade | 21 | 0.10 | 0.05 |
| spell | 14 | 0.04 | 0.25 |
| travel | 28 | 0.02 | 0.09 |
| conversation | 21 | 0.00 | 0.00 |

The diagnosed lines, errors over both scorers, before and after: the climb made "by 0" 12
to 0, the dying bandit 8 to 0, cruelty (the declared fight) 7 to 0, the wait 6 to 0, the
job taken 4 to 0, the trip 4 to 0, the declared punch 10 to 3, the harvest 18 to 6, the
theft 6 to 2, the price agreed 6 to 3, the gallows walk 6 to 3; crafting at a bench 4 to 4,
the shot 3 to 3.

### What remains (53 errors over both scorers)

| slot | writer | cause | share |
|---|---|---|---|
| act | slot's first answer | invention (by code) | 51% |
| act | slot's first answer | omission: the slot never wrote it | 17% |
| act | cut by `_repair_sentences` | omission: written, then cut | 8% |
| tail | `_repair_sentences` (its rewrite or line) | — | 9% |
| enemy turn: act (blow) | slot's first answer | omission, invention | 6% |
| engine | the engine's page line ("The fight is over.") | — | 4% |
| act | slot's first answer | copied from the shared prompt | 4% |

The enemy-turn beats went from 11% of the errors (free prose) to 6% (planned). The share
written or cut by our own repairs rose to about a fifth (`_repair_sentences` 9 of 53), and
it writes or cuts the most Q pages after the slots themselves (10 of 91), with the tells
check's engine-line fallback next (7).

Top remaining patterns, by count over both scorers:

1. Who comes for the player on an arrest: the shopkeeper counted among the arresting
   watch (5).
2. Walking to the gate told as entering the town (5).
3. The harvest: a made Survival check told as a ruined hide (4), the sinew left out (2).
4. Crafting: the finished belt cut by `_repair_sentences` (4).
5. Magic missile: the count of missiles wrong, or its damage left out (5).
6. The price agreed: still told as a payment inspected (3).
7. A repair's own line in a declared fight ("Whatever you reach for does not answer") (2).
8. A repair's rewrite of a made Perception check into murk (2).
9. The engine's "The fight is over." with a robber still standing (2).
10. An enemy's trip on the player ("knocked prone") left out of its planned beat (2).

And two new page shapes worth a look: the intimate invitation is now told twice, the second
time turned into asking for a room (7 S tags, 10 Q) — the say tell carries only "up to my
room" of the line; and the gallows walk opens on a fragment the tells check's engine-line
fallback leaves ("to his execution."), or turns third person ("and he dies").

Seconds a turn (wall, in-process, less Ollama's loads, the 301 pairs): baseline median 30.9
(non-fight 30.5, fight 59.2), fixed 30.3 (non-fight 29.8, fight 58.9); model calls median 12
in both. **No cost in time.**

## Round 2: the pipeline and the reader (2026-11-05, branch fix/narration-r2-pipeline)

The trial denial's regression, `_repair_sentences` on planned beats, the tells check's
fallback, and the invitation told twice. A parallel lane did the engine, the tells and the
slots. Tests: `tests/test_narration_r2_pipeline.py`, one per defect.

**A new instrument: the offline replay** (`drive.py replay`). Every model call of a recorded
turn is answered with the reply it got then, matched by caller and slot in order, so the
rerun's 308 recorded turns play again on changed pipeline code with no model. On unchanged
code it reproduced 271 of 308 pages exactly (the misses are fights, where the watcher's
thread and the turn-spanning caches of the reads take another path). It is exact up to the
first call the changed code makes differently; after that, recorded replies can be served to
the wrong call, so every page below was read by hand, and the live bench is the measure.

### 1. "I swear I never touched her" (regression, fixed)

Why: the reader's frame. Before 8c6cf4e8 it read the denial as the `claim` act ("assert who
or what you are"), which owes no op, so the planner made a say and the turn narrated — by
luck, since the act was as wrong as what replaced it. After, it wrote no deed and
`claims: ["I never touched her"]`, and the means gate asked `claim_kind` about the claim
alone, which came back "declared true", and refused the turn. Ablated at temperature 0 and
0.7 (frozen copies of the reader, nothing else changed): reverting the commit's attack gloss
alone brought the `claim` act back (1 of 1; 3 of 4), but reverting the gloss AND the two new
demonstrations did not (0 of 1; 1 of 4), nor did reverting every prompt change while the
`blow` field stayed in the schema (0 of 1; 2 of 4). No one part does it: the line sat on a
knife edge between two wrong readings, and nothing in the prompt demonstrated a denial.

Fixed twice over, because the reader is the source and the gate is the net:

- the reader is shown that an oath and a protest are talk with their words in `says` (two
  demonstrations, neither a probe nor a labelled line; `interpret._DEMOS`);
- a bare claim is asked once, before anything is built, with the whole line beside what it
  states, and a fourth answer, "said aloud", turns the frame into the talk it is
  (`means.said_aloud`, `claim_kind`). The line alone was tried first and turned the means
  corpus's "I decide that the smith owes me fifty gold" into "a plan" (6 of 6); line and
  statement together sort 10 of 10 probe pairs as intended.

| reader probe (heretic) | before, 0.7 ×6 | after, 0.7 ×6 | before, 0 ×2 | after, 0 ×2 |
|---|---|---|---|---|
| the trial denial read as talk | 0/6 (refused 6) | 6/6 (refused 0) | 0/2 | 2/2 |
| eight lines of speech (denials, pleas, oaths) as talk | 24/48 | 42/48 | 8/16 | 14/16 |
| six finishing-blow lines, `blow: finishing` | 36/36 | 36/36 | 12/12 | 12/12 |
| six ordinary blows, ordinary | 36/36 | 36/36 | 12/12 | 12/12 |

"I insist I was at the tavern all night" still comes back the `claim` act (0 of 6) — not
refused, since it is not bare. The means bench (dev corpus, as the turn runs it): refused
76/87, spared 89/89, declared results spared 9/9; the same bench with the reader frozen at
80ed1ef4, 75/87, 89/89, 9/9. **Both are below the 86/87 docs/means-gate.md recorded on
2026-10-08** — drift from earlier reader changes, not this one; the misses are minds read
and walls seen through, read `ordinary`.

### 2. `_repair_sentences` on planned beats

Which checks fire on planned beats, on the rerun (findings over 301 turns), and what each
now does. Every act slot of a planned beat was already read against its own tells, so a
member may stand aside (`PLANNED_OFF`), be backstopped without a rewrite
(`PLANNED_NO_REWRITE`), or be kept; and **no repair may leave an act slot's tells untold**:
a slot that had a sentence before the repairs and has none after gets its tells' engine
line where its sentences stood (`agent.keep_act_slots`, the tells check's own fallback).

| check | planned findings | what they were | decision |
|---|---|---|---|
| light-left-off-the-page | 17 | gloom folded into a slot sentence 13 times, harmless; once a made Perception check into murk | kept; a search owes the gloom only when the check failed (`light_shown._searching`) |
| beat-condition | 10 | "stuns" rewritten off (8); the trip's only sentence cut once | kept; the cut is now protected |
| beat-foe-struck-with | 7 | all false: the stat block's "guisarme" against the engine's "mwk guisarme"; the slot's blow replaced by the engine's line 7 of 7 | fixed in the check (`beat_verify._same_weapon`) |
| land-not-described | 7 | no repair made | kept |
| beat-setting | 7 | a "general store" in the open market, rewritten | kept |
| power-unbacked | 6 | 1 fixed by the rewrite, 4 "still did it"; the backstop's refusal line shipped 3 times ("Whatever you reach for does not answer") | no rewrite; cut without the line (a declared reach is refused before a planned turn) |
| beat-settles-trade | 5 | true: a payment told on the agreed price | kept; the cut is protected (the engine's payment line now stands in) |
| road-claimed | 4 | all false: the player asking about a road; 2 cut the ask | off |
| speaks-for-the-player | 3 | 2 fine; the third the invitation's invented "a room" | kept (item 4 is the source) |
| stop-not-shown | 3 | all false: the slot had shown the stop; the backstop pasted the engine's meeting line beside it | off |
| beat-makes-item | 2 | both false: the belt's making read as another item; the belt cut | off |
| route-not-walked | 2 | rode with the stop | off |

Replayed offline (the 22 changed pages on turns the unchanged replay reproduced, read by
hand): the finished belt stays on the page (craft, runs 1 and 5); the refusal line is gone
from the three pages that had it (punch, run 2; skin, run 7; crude, run 7); the made climb
is no longer murk (run 7); the agreed price gets the engine's payment line back where the
cut left nothing (runs 4 and 6); the road question keeps its own sentence (runs 3 and 5). Of
the rerun's scored items, 13 quoted on these pages are no longer on them (7 of scorer A's,
6 of B's), and the belt's two omissions (which quote the tell, not the page) are told. Worse, seen: on ask-road runs 4 and 7 the ask is now told twice — the
deed backstop (`_show_declared`, outside `_repair_sentences`) judged the slot's ask unshown
and wrote it again, and road-claimed's cut used to delete that copy by chance. Left for the
deed reader.

### 3. The tells check's fallback

The fragment was not the engine line: it was a cut. The sentence splitter ended a sentence
at the player's initial ("…accompany Mira H. to his execution."), the check flagged the
first half, and the cut left "to his execution." as the whole act slot; the example-cast
pass, rejoining at the same stop, wrote "around you' s neck". Now: a lone capital's stop
followed by a lowercase word or "'s" ends nothing (`narration._SENTENCE`; a capital after
it still does); a cut leaves whole sentences or nothing (`planned.cut_slot_sentence`), and
nothing left means the engine's line (`planned.engine_line`: page line, brackets and the XP
line off), which the groom's un-naming and second-person steps run over — "You go along
with the escort toward the market, held." Replayed: both gallows pages open on that line,
and "your neck". A say's reported words are closed as a sentence when carried
(`judgement._said_whole`), so the say tell no longer runs into "You are in conversation…".

Not fixed here: "and he dies instantly" is the act slot's own words (the slot named the
player, and the second-person swap cannot resolve the pronoun after it without reading
English). The slots lane's.

### 4. The invitation told twice

The reader split "I invite the innkeeper up to my room to share my bed tonight" into a talk
saying "up to my room" and an intended talk "to share my bed tonight", and the say carried
the first. Now the words said run on through the speech acts whose spans follow in one
breath, to nobody else, and reported speech is carried from its own verb — the reader's
span, not only its `says` (`interpret.words_said`: spans and their places, no English read;
a quotation is still the quotation as typed). A say carrying part of the line carries all
of it (`judgement.own_words_only`), closed as a sentence.

Measured live, each step: carried as "up to my room to share my bed tonight" (the run-on
alone; with the new demonstrations the reader also read the line as one talk), the
invitation was told once on 5 of 5 runs but still as asking for a room ("you request a room
to share your bed"); carried from its verb, "invite the innkeeper up to my room to share my
bed tonight", it was told once and as the invitation on 3 of 3 ("you suggest that they come
up to your room to share your bed tonight"). The price, on the other lines that speak:
the threat ("tell [the stallholder] I'll gut her like a fish …") came back once in 4 runs as
the quotation "Tell them I'll gut you like a fish if you say one word to the guards" (0 of 7
on the rerun); bluff,
crude, the healer, the road, the job, "when it will be ready" and the plea read as before
or better ("You fall to your knees and plead for mercy" where the words had been "mercy").
The fade is untouched; nothing explicit is written.

### 5. The made Perception check written as murk

`_repair_sentences`, not the tells check's remake: the light check's rewrite (item 2).

### The bench (live, paired, blind)

The affected lines on this branch, paired by item, run and Ollama seed with the rerun's
fixed turns: the trial denial (4 runs), crafting (3), the two declared fights (3 each), the
climb with its Perception check (3), the gallows walk (3), the intimate invitation to the
fade (3), and — for the say carried from its verb — the other lines that speak (threat 4,
bluff 2, crude 2, the healer, the road, the job, "when it will be ready", the plea). 35
turns beside 35, shuffled into one blind set, two scorers (agents), the same rubric. The
trial denial's "before" is the original baseline's (it narrated; the rerun refused it), so
its pages carry round 1's own fixes too and are counted apart below.

| | errors / beat, A (95%) | B (95%) | Q pages A / B | S A / B | rating A / B |
|---|---|---|---|---|---|
| before, all 35 | 0.200 (0.057-0.371) | 0.200 (0.057-0.371) | 7 / 7 | 0 / 3 | 3.11 / 3.20 |
| round 2, all 35 | 0.029 (0.000-0.086) | 0.057 (0.000-0.143) | 3 / 3 | 0 / 0 | 3.49 / 3.60 |
| before, the 31 beside the rerun | 0.129 (4 errors) | 0.129 (4) | 7 / 7 | 0 / 3 | |
| round 2, the same 31 | 0.032 (1) | 0.065 (2) | 3 / 3 | 0 / 0 | |

- Agreement: the same has-an-error verdict on 69 of 70 beats (kappa 0.93); 8 of 8 of A's
  errors also B's. Paired by beat, fewer/more: A 6/1 (sign p 0.12), B 6/2 (p 0.29) — 35
  pairs is few, and the intervals overlap.
- The trial denial: refused 7 of 7 on the rerun; **narrated 4 of 4** here, with no error
  on its pages (the baseline's three were the verdict told as passed, round 1's fix).
- Gone: the belt never told (craft, runs 1 and 5: 2 E6 each scorer), the refusal line in
  the declared punch (run 2), the gallows fragment and "you' s neck" (runs 1 and 4), the
  invitation told as a room (3 of 3 before, 0 of 3 after: 3 Q each scorer, 3 S for B).
- Left, all slot-written: the gallows page still slips into third person ("You are hanged
  for murder and falls silent, his life extinguished", run 1; "his life ending before the
  town's gates", run 3, an E8 for both); the matter slot's "You must spend your remaining
  coins" on a hanged man (run 1). New, from the say carried from its verb: the threat as the
  quotation "Tell them I'll gut you like a fish …" (run 1 of 4, a Q for both). B also marked
  "the blade will be ready for you" (an E7, the commission's own longsword).

**Seconds a turn: 31.1 → 52.9 median (wall less model loads), and it is contention, not
the change.** Calls a turn went down (14 → 13); every kind of call ran 1.3-3.1 times slower
than on the rerun, prompts unchanged or not (the beat read 1.04 → 2.69 s, the unbacked-power
read 0.60 → 1.67, the slots 1.70 → 3.65), while the parallel lane shared the one Ollama. The
reader's two new demonstrations are the only prompt that grew.

### Limits

- Scorers are two agents of one model family. The rerun's "before" pages were scored again
  in this set, beside the new ones.
- The replay is exact only up to the first call the changed code makes differently, and the
  initialled name changes sentence numbering, so replayed reads land on other sentences on
  those saves; the replay was used to find and read the changed pages, never to score them.
- Not built: `_show_declared` writing a slot's shown ask again (ask-road runs 4 and 7, seen
  in the replay); the slot's third-person pronoun for the player; "I insist …" still read as
  the `claim` act; the means gate's drift from 86/87 to 75-76/87 on its dev corpus.

## Round 2, the engine side (2026-11-05, branch fix/narration-r2-engine)

The rerun's remaining patterns that came from engine facts, tell wording or slot content.
Each wording was settled by re-asking the recorded slot call (heretic, temperature 0.8, the
slot's own schema) with only that text changed, before any code moved; the counts are in
the code's comments and in `tests/test_narration_r2_engine.py`, one test per defect. The
parallel lane's territory (`_repair_sentences`, the engine-line fallback, the trial-denial
reader, the intimate say) was left alone.

| pattern (rerun errors) | what the narrator was told | what it is told now | re-asked before → after |
|---|---|---|---|
| the shopkeeper among the arresting watch (5) | "<the captain>, the guardsman and the second guardsman come for X" — the engine's arresters were right | "Three of the watch come for X, and only they: …" (`arrest.who_come`), and PEOPLE HERE says "of the watch" by `has_state(GUARD)` | shopkeeper added 3 of 6 → 0 of 6 |
| walking to the gate told as entering the town (5) | "the guards at the gate look twice, and let you through" on a walk that stopped inside | "… know it, look twice at you as you come up, and keep their eyes on you. You stand on the inner side of the gate: still in X, and the way out is beyond it." "Let you through" only on a crossing | passed through 6 of 6 → inside 8 of 8 ("let you be" still came back "let you pass") |
| a ruined sinew told as the hide ruined (4), the sinew left out (2) | one run of prose per part, "it comes away, but not cleanly", the roll lines between | "X cuts two parts from the wolf, each on its own check. The wolf pelt: peeled off and kept, 1 unit, in the pack (…). The sinew thread: ruined in the taking, and none of it is kept (…). The ruin is the sinew thread's alone: …" (`engine._harvest_fate`, read off `harvest.take`'s new closed `fate`) | pelt kept beside a ruined sinew 8 of 8; sinew told as a part kept 0 of 6 → 8 of 8 |
| one missile told as two or three, or its harm left out (5) | "1d4+1 — 3. the robber takes 3 untyped." | "One missile of force flies, the only one a caster of level 1 makes: it strikes the robber for 3 (…)", and the cast carries its harm as blows (`Outcome.blows`), so the act slot is a blow slot | plural 7 of 8 → 0 of 12, the wound told 12 of 12 |
| a price already paid told as paid now (3) | "pays nothing more: the smith took the fee with the job"; and the player's line rode the smith's own `say` | "X paid the smith earlier, when the job was taken, and owes nothing now: no coin changes hands this time." (`commission.paid_before`); the line rides only an act of the player's | coin taken now 5 of 6 → 0 of 8; "inspect the payment" 4 of 6 → 0 of 8 |
| the bow shot told as a hit and as still being readied (3) | the joined tell's "Nothing has landed yet" beside the hit it rolled at once, and the act asked as a declaration | the joined tell says the first blow comes at once (`Engine._their_first_blow`), and an act that struck its blow is a blow slot | — |
| an enemy's trip on the player left out (2) | the trip only in the act's tells, which the bite's second slot never sees | the blow carries it: "…; then the wolf's trip takes: you are knocked prone" (`Engine._rider_then`, `blows[…]["then"]`); "hurt and slowing" (read as slowed) is gone from the bands | — |

Engine defects, fixed:

- **"The fight is over." with the robbers standing** (2 errors): `sides_standing() <= 1`
  ended the fight whichever side fell. When the player's side has nobody standing it is
  now said as lost, with who stands over them, and a player dying or out cold is left in
  the fight for the downed door (`downed.resolve`), which bleeds them, ends it when they are
  stable and lets the winners act (`views._side_lost`). A held player's fight still ends.
- **A caster struck down by the provoked blow cast anyway**: "unconscious and dying … holds
  Burning Hands together … the robber takes 2 fire". `_concentrate` now asks
  `blocking_key("cast")` first: the spell is lost, no check rolled.
- **Magic missile made one missile at every caster level**: `spells.missiles_at` (CRB p.310,
  one plus one per two levels past 1st, five at most), each missile its own share of the
  faces, dealt over the targets in turn; a target past the last missile is told so (every
  target named used to take the whole roll).
- **An actorless intent on a creature's turn was the player's** ("<the player> has no ability
  called Booming Voice"): `agent._owned_by` gives it the creature, and refuses the player as
  actor with the fix named.
- **A beast died in a humanoid's words, with broken agreement**: beasts (`states.is_beast`:
  `type.animal`, `type.magical-beast`, `type.vermin`) have their own death lines, and `_fill`
  makes every verb agree with its own subject (the old fix covered only the verb right after
  the name: "staggers … and sit down … and are dead").
- **A harvest that kept parts did not back the page that packed them**, found on this
  lane's bench: "stow them safely in your pack" was cut as an invented haul because
  `harvest` (and `make`) were missing from `claims_the_engine_backs`' gathering doors, and
  the beat shipped with no harvest on it.

Crafting at a bench (4 errors in the rerun): nothing left in the tell or the slot. In the
recorded runs the slot wrote the belt finished ("a sturdy belt is finished and packed
away"); the truth checks' `beat-makes-item` finding read "a sturdy belt" as an item the
engine did not make (it made "Goat Belt"), and `_repair_sentences` cut the sentence. That
finding and that cut are the parallel lane's. On this bench crafting scored 0 errors in 7.

### The bench

The nine lines (arrest, gate walk, harvest, magic missile, price agreed, burning hands — the
robber fight —, the shot with the enemy's trip, the player's trip, crafting), runs 1-7 each
on 40e107d1, paired by item, run and Ollama seed with the rerun's fixed turns of the same
lines: 63 turns beside 63, one blind shuffle, two scorers (agents), the same rubric
(`blind.py`, `attribute.py`).

| | rerun, fixed (63 beats) | round 2 (63 beats) |
|---|---|---|
| errors / beat, scorer A (95% bootstrap) | 0.317 (0.190-0.444), 20 errors | 0.111 (0.032-0.222), 7 |
| errors / beat, scorer B | 0.317 (0.190-0.444), 20 | 0.063 (0.000-0.143), 4 |
| beats with an error, A / B | 30% / 30% | 8% / 5% |
| Q pages, A / B | 14 / 14 | 3 / 6 |
| prose rating, A / B | 2.89 / 2.79 | 3.35 / 3.14 |

Paired by beat: fewer on 17, more on 4 (sign test p = 0.007, A); 17 / 2 (p = 0.0007, B). By
line, fewer on 6 of 9, more on 1 (p = 0.125 for both; nine lines are few). Agreement: the
same has-an-error verdict on 124 of 126 beats (kappa 0.95), 85% of A's errors also B's.

By line, errors over both scorers, before → after: arrest 8 → 0, gate 6 → 0, magic missile
10 → 2, price agreed 4 → 0, crafting 4 → 0, the shot 4 → 1, harvest 4 → 4, burning hands
0 → 4, trip 0 → 0.

What round 2 still got wrong (11 over both scorers):

- the harvest's 4: one beat (run 4) whose true harvest sentence the claims scrubber cut
  (the defect above, fixed after this run, 832af8c0); the attribution names it a slot omission
  because it cannot see that cut;
- burning hands' 4: an enemy's close miss written "only to graze your side" twice (a blow
  slot inventing past "a near thing, only just turned aside", and the tells check passed
  it), and once the spell's damage left out of an act that held two attacks of opportunity,
  the cast, and a second, refused cast the planner wrote;
- magic missile's 2: a caster struck down before casting, written "As you attempt to conjure
  a magical defense";
- the shot's 1: an ally's hit written "strikes the wolf's flank but is turned aside".

The harvest line rerun with the claims fix (runs 1-7, 832af8c0), blind beside the rerun's
fixed harvest turns, two scorers: 0 errors in 7 beats on both scorers (the fixed side, scored
afresh: 1 and 1, "ruining the integrity of the hide"). All seven pages tell each part's fate
as its tell says, the torn pelt and the rough sinew included.

**The gallows page's third-person slips** (handed over by the pipeline lane): "snaps <the player character>
into the air, and he dies instantly". The name is turned to "you" downstream
(`pc_to_second_person`); the "he" cannot be, without reading English. In the slot: an act
whose tells name the player's character now says who that is — "<Name> is the player's
character: "you" in every sentence, never "he", "she" or "they"." Re-asked with
the recorded call: third person 8 of 8 → 0 of 8. Putting the tells themselves in the second
person also gave 0 of 8, but changes the wording of every act slot the other measurements
were made on (and `pc_to_second_person` leaves "owes", "their way out" unagreed), so it was
not taken. The arrest, price and harvest asks re-asked with the sentence added held their
counts (0 of 6, 0 of 6, 6 of 6 pelts kept). The gallows line, runs 1-7, blind beside the
rerun's fixed runs, two scorers: no E errors on either side (as in the rerun's own scoring
of this line); Q pages 6 and 6 → 2 and 3; the third-person death (1 beat, both scorers) and
"around you' s neck" gone. The Q left: the matter slot giving a dead character "the road
ahead" (2), and "You walk with the condemned to the gallows" (1). These runs were on this
branch alone, without the pipeline lane's engine-line fallback fix.

Seconds a turn: the medians (58.8 against 30.8) were taken with the full suite running for
most of the bench and the parallel lane on the same Ollama, and are not a measurement; model
calls a turn fell, median 16 → 14.

Limits: the scorers are one model family; the new tell wording is visible on the sheets; the
fixed side is the rerun's recorded turns, so the dice diverged wherever a turn's calls did
(two of seven magic-missile runs and one burning-hands run had the caster struck down before
the spell, which the old engine would have let them cast). The shot's runs were made before
the joined tell was given its article ("squares off against wolf", fixed in 31614427).

## The final rerun (2026-11-05): round 2, the release verdict

The same 44 lines, snapshots and default condition, 7 runs each (308 turns), on 82e6348b
(round 2: the pipeline lane and the engine lane), paired by line, run and Ollama seed with
the baseline and with round 1. The driver ran unchanged against the new code (a condition
name was added); the tracer's planned-beat keys held for the new enemy turns.

Ollama was uncontended: `ollama ps` every two minutes through the run showed only the
heretic model in all 92 readings; model loads came to 101 s over 308 turns.

The trial denial narrates again on all 7 runs. It is in the baseline and round 2 (308
each); round 1 refused it before the turn, so round 1 has 301 turns and round 2 is
compared with it over those 301 pairs.

**Blind, three-way.** The 308 baseline, 301 round-1 and 308 round-2 turns in one shuffle
(917 items), conditions hidden, two scorers (agents), the same rubric. Where their error
counts differed (29 of 917 items) a third scorer read those items alone, shown neither
answer, and its count stands (`tools/narration_diag/adjudicate.py`); elsewhere the agreed
count stands. Agreement before adjudication: same has-an-error verdict on 890 of 917
(kappa 0.83), Pearson r 0.86, 79% of A's errors also marked by B. The new tell wording makes
the fixed conditions somewhat recognisable.

| | baseline | round 1 | round 2 |
|---|---|---|---|
| beats | 308 | 301 | 308 |
| errors / beat, adjudicated (95% bootstrap) | 0.192 (0.143-0.240), 59 | 0.073 (0.043-0.106), 22 | **0.032 (0.013-0.055), 10** |
| errors / beat, scorer A | 0.208 (0.159-0.256) | 0.086 (0.053-0.123) | 0.045 (0.023-0.071) |
| errors / beat, scorer B | 0.192 (0.143-0.240) | 0.076 (0.047-0.110) | 0.039 (0.016-0.065) |
| beats with an error, adjudicated | 53 (17%) | 22 (7%) | 11 (4%) |
| prose rating, A / B (1-5) | 3.06 / 3.07 | 3.08 / 3.11 | 3.20 / 3.22 |
| broken pages (Q), adjudicated | 44 | 42 | 38 |
| softened (S) | 0 | 5 | 1 |
| refusals, moralising | 1 (a remake out of character), 0 | 0, 0 | 0, 0 |
| seconds a turn, median, less loads (non-fight / fight) | 30.9 (30.6 / 59.2) | 30.3 (29.8 / 58.9) | 30.6 (30.2 / 60.6) |

**Paired** (adjudicated; A and B in brackets):

| | by beat, fewer / more (sign p) | by line, fewer / more (sign p) | difference a beat, lines resampled (95%) |
|---|---|---|---|
| round 2 vs baseline | 50 / 7 (4e-9) [55/8, 54/8] | 19 / 4 (0.003) [20/5, 21/5] | -0.15 (-0.24 to -0.07) |
| round 2 vs round 1 | 21 / 10 (0.07) [24/12 p 0.07, 20/8 p 0.04] | 11 / 4 (0.12) [11/5, 10/3] | -0.04 (-0.08 to 0.00) |
| round 1 vs baseline | 47 / 18 (0.0004) | 18 / 5 (0.011) | -0.11 (-0.19 to -0.03) |

**Round 2 against the baseline is a large, clear drop: 0.19 to 0.03 errors a beat, beats
with an error from 17% to 4%.** Round 2 against round 1 points the same way on every
measure and scorer and is at the edge of significance (one scorer's beat test p = 0.04, the
adjudicated p = 0.07; the interval just reaches zero): the second round removed most of
what was left, but 300 beats a side cannot prove a difference of 0.04 a beat on its own.

| activity | beats | baseline | round 1 | round 2 |
|---|---|---|---|---|
| loot and harvest | 14 | 0.64 | 0.21 | 0.07 |
| commission and craft | 21 | 0.43 | 0.19 | 0.00 |
| skill check | 14 | 0.36 | 0.00 | 0.07 |
| fight | 35 | 0.31 | 0.09 | 0.03 |
| theft | 14 | 0.21 | 0.07 | 0.07 |
| mature | 35 | 0.20 | 0.00 | 0.03 |
| arrest and trial | 49 (42) | 0.18 | 0.12 | 0.02 |
| quest | 14 | 0.14 | 0.00 | 0.00 |
| wait and sleep | 28 | 0.11 | 0.04 | 0.04 |
| spell | 14 | 0.07 | 0.29 | 0.29 |
| travel | 28 | 0.00 | 0.07 | 0.04 |
| conversation, trade | 42 | 0.00 | 0.00 | 0.00 |

Spells are the one activity that got worse and stayed worse (1 error in 14 baseline beats,
4 in round 1, 4 in round 2): the enemy's blow inside the casting turn left out of the
spell's planned beat, and the repair rewriting an enemy's miss.

### What remains in round 2 (10 adjudicated errors)

| slot | writer | cause | errors |
|---|---|---|---|
| act | slot's first answer | omission: the slot never wrote it | 3 |
| act | slot's first answer | invention | 3 |
| act (blow, a spell's turn) | slot's first answer | omission: an enemy's blow in the act left out | 2 |
| tail | `_repair_sentences`' own rewrite | names the wrong target of an enemy's miss | 2 |
| enemy turn: blow | slot's first answer | invention | 1 |
| act | cut by `_undeclared_blows` | an arrival's demand cut | 1 |

(Over the two scorers' lines: 12 errors in round 2, 75% the slots' first answers, 17% a
repair's rewrite, 8% a cut.) No pattern repeats more than twice:

1. Spells: the enemy's blow during the casting turn left out (2), and the repair's rewrite
   of an enemy's miss pointing it at the wrong person (2).
2. A declared assault: the warrant in the same tell left out (1; 13 in the baseline).
3. A theft unseen: the watch coming left out (1).
4. A wait: one of the arrivals the tell lists left out (1).
5. A made climb told with an extra deed; a made harvest told as stripped clean when one part
   failed (1 each).
6. Going quietly told with the player "silent" (1).
7. The gate: an arrival's demand cut by the undeclared-blow backstop (1).
8. An ally's hit told as a miss in an enemy-turn beat (1).

Broken pages (38) are now the larger share of what a reader would notice: the gallows walk
(7: the dead man still offered "what do you do?", or told to gather supplies, often from a
tells-check remake), the commission (7: the request told twice, a re-ask's "It is
finished" before the work), the killing blow (4) and the trial denial (3).

### Limits

- Scorers are agents of one model family; adjudication resolves their disagreements, not
  their shared blind spots.
- Round 1 lacks the trial denial (refused then), so round 2 is compared with it on 301
  pairs and with the baseline on 308.
- The same seed reaches the same call only while a turn makes the same calls; engine
  outcomes still differ between conditions on some lines.

## Round 3 (2026-11-05, branch fix/narration-r3): the three leftovers

The owner chose one more short round on what the final rerun left, then the build. Tests:
`tests/test_narration_r3.py`, one or more per defect, the measurement in each docstring.

### 1. Spells

**(a) The enemy's blow in the casting turn.** An attack of opportunity the cast provoked,
not an enemy turn folded into the act. It resolved before the spell's damage roll, the batch
waited for the player's die, and the done outcomes were parked as dicts; `engine._rehydrate`
brought them back without `Outcome.blows`. So the spell's blow slot was handed THE BLOW of the
spell alone, every time a cast provoked and the player rolled damage (the club's 3 on burning
hands run 3, the robber's 4 on magic missile run 4). The blows now ride the round trip, and
the provoked blow is a line of the act's own THE BLOW facts ("HIT — the robber at you —
weapon: club …"), in order, before the spell's.

**(b) The miss told as aimed at the wrong man.** `light_shown`'s `light-miss-unshown`
rewrite: its anchor is the first sentence about any blow, which on a turn of several blows
is often somebody else's, and the rewrite folded "the robber finds nothing there" into the
sentence about the second robber (runs 1 and 3; on run 3 over a sentence that had told his
hit). Of the rerun's four findings of this kind on planned beats, the two rewrites kept were
these two errors. It is now `PLANNED_NO_REWRITE`: the backstop's line names nobody and says
"at you" only when the engine's record says the blow was at the player (which the restored
blows now let it read).

### 2. The dead character's page

- `planned.build_plan`: when the player's character is dead (`state.down.dead`, read after
  the turn resolved) the beat is its acts — no matter, aside, reply, ground or "still" slot,
  and no suggestions asked. The matter slot and its tells-check remake were what wrote "the
  road ahead" and "just enough coin to gather the supplies".
- `GMAgent._groom`: no hand-back on a dead character's beat, and a closing question a slot
  or the free narrator wrote is taken off (`narration.drop_hand_back`, the final unquoted
  question only); "That's wrong" on such a page the same (`remake_planned`). The death
  screen then takes over as before (`views._the_player_died`, unchanged). The tells-check
  remake uses the slot's own call, whose system prompt already forbids a question, and the
  matter slot it remade on runs 2 and 7 is no longer asked at all.
- `rules.intents.claims_the_engine_backs`: a `condition` effect of "dead" backs "you are
  dead" — run 5's "You are dead." had been rewritten "You are breathless." by the
  outcome-claims repair.
- On the bench below two slots read the trial's "before the town" as time ("Before the crowd
  can gather", "before the town can witness your final moments", 2 errors). Re-asked with
  the recorded calls, 7 runs × 3: read as time 5 of 21; worded "with the town looking on",
  0 of 21 (`rules/trial.py`). The gallows line rerun on that wording, 7 runs, scored blind
  on their own: 0 errors on both scorers, 1 Q page.

### 3. The commission

**Not told twice: told backwards.** On the final rerun the request was never told twice on
the commission line; the scorers' notes on its 6 broken pages are "request told after the
result; events told backwards" (7 of 7 runs, and the same in the baseline and round 1). The
reader reads "I ask the smith to forge me a longsword" as one `commission` span; the say is
injected from the same words and runs last (`judgement.inject_say`), and the slots followed
the outcomes. `planned.ask_before_the_deed` moves the player's say before the first act of
theirs about the person spoken to, when the say's words lie inside a deed's span (spans
and their places; no English read). Speech the reader read as its own act keeps its order.

**"It is finished" on spoiled work.** The reply, not the act slot: the made-up-work re-ask
of the smith's reply (run 2), and the reply generally answering as if nothing had happened
("I'll have it ready once I've hammered the shape true"). The reply is now given the
commission's own tell (`planned._their_own_work`, matched by `Outcome.about`), and a spoiled
job's tell says "no job is taken: nothing is being made for <the player>"
(`rules/commission.py`; the fact is in the tell, law 3). Re-asked with the recorded reply
calls, 4 spoiled runs × 4: done, promised or held as a job 13 of 16 as recorded; 7-9 of 16
with the act's line; 3-5 of 16 with the no-job sentence too (judged by hand).

**Ask-road told twice** was round 2's replay only (runs 4 and 7, not the live rerun):
`_show_declared` wrote again an ask the say slot had shown, because the deed reader judged it
unshown. A speech deed whose say an act slot carries is now that slot's to tell
(`agent.said_by_its_slot`).

### The bench (live, paired, blind)

On 1a364334 (before the trial rewording), the affected lines 7 runs each (magic missile,
burning hands, gallows, commission, agree, ask-road: 42 turns) and the other 38 lines 2 runs
each (76 turns), paired by line, run and Ollama seed with the final rerun's round-2 turns:
118 beside 118 in one blind shuffle, two scorers (agents) and the adjudicator on the 4 beats
whose counts differed. Ollama uncontended (only heretic loaded; nothing else running).

| | round 2 (118) | round 3 (118) |
|---|---|---|
| errors / beat, adjudicated (95% bootstrap) | 0.059 (0.017-0.110), 7 | 0.042 (0.008-0.085), 5 |
| scorer A / B | 0.051 / 0.068 | 0.042 / 0.059 |
| broken pages (Q), adjudicated | 22 | 8 |
| prose rating, A / B | 3.06 / 3.17 | 3.20 / 3.31 |
| softened, refusals, moralising | 0, 0, 0 | 0, 0, 0 |
| seconds a turn, median less loads (affected / all) | 32.0 / 31.1 | 29.2 / 29.7 |
| model calls a turn, median | 13 | 12 |

Agreement (A, B): the same has-an-error verdict on 233 of 236 beats (kappa 0.87), 10 of 11 of
A's errors also B's. Paired by beat, round 3 fewer on 5, more on 4: **118 beats a side cannot
show the error rate moved**; the broken pages can (22 → 8).

| line (adjudicated) | errors r2 → r3 | Q pages r2 → r3 |
|---|---|---|
| magic missile | 1 → 0 | 0 → 1 |
| burning hands | 3 → 1 | 1 → 1 |
| gallows | 0 → 2 (→ 0 reworded) | 7 → 1 (→ 1 reworded) |
| commission | 0 → 1 | 6 → 0 |
| agree | 0 → 0 | 0 → 1 |
| ask-road | 0 → 0 | 0 → 0 |
| the other 38 lines (76 beats) | 3 → 1 | 8 → 4 |

Spells 4 errors in 14 beats → 1: the provoked blows are told on the r3 spell pages that had
them, and no light miss was rewritten. The one left is an enemy turn's blow slot writing a
miss "glancing off your form" (burning hands run 5). Every gallows page ends on the death
(7 of 7 ended "What do you do?" before; 0 of 7 now, and 0 of 7 on the reworded rerun) with no
road, supplies or aside. Every commission page tells the ask first; its one error is the act
slot's "a poor blade of pewter that is ruined" against "nothing is ruined".

What the r3 pages still got wrong or broke, none from code this round changed:

- agree run 4: the engine's raw refusal on the page, item ids and all ("… is not carrying
  blade-blank-1. They have: backpack#1, …"), pasted by `beat_verified`'s
  `beat-omits-outcome` backstop. The planner made a `sell` this run (not in round 2's runs of
  the line), and the refusal's wording is the inventory's. Not fixed here.
- gallows (reworded rerun) run 2: the refused walk's "Still for you to choose: slip their
  hold … or go along" told, then the hanging — the planner made a refused travel before the
  trial. Not fixed here.
- cruelty run 2: the warrant left out (round 2's same run too).
- burning hands run 6: "Your previous spell remains", the slot reading a second, refused cast
  the planner wrote ("What was cast before it stands").

### Limits

- Scorers are agents of one model family. Round 2's turns were scored afresh in this set.
- 118 beats a side; the affected lines are 7 runs each. The gallows rewording was measured on
  its own 7 runs, scored blind on their own, not beside round 2.
- The same seed reaches the same call only while a turn makes the same calls: the spell lines'
  dice differ between the sides on most runs (a different set of provoked blows landed).
