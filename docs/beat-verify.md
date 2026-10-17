# The beat read back: verification by round trip (lane V)

The owner, 2026-10-03, after a day of regex checks that each exposed the next:

> "we cant really depend i think on just layering mechanical detection logic on top this
> will be an endless loop"

and then:

> "could we have the interpretor/one of these smaller models read the final text convert
> it back to json and make sure that it matches the expected actions?"

This is that check. It is `docs/structured-turn.md`, Backward §4 ("Policing … the next
step"), built.

- `gm/beat_verify.py` is the reader and the diff.
- `gm/checks/beat_verified.py` is the registry member.
- `tests/beat_verify/gold.py` is the bench.
- `tools/beat_verify_bench.py` runs it.
- `tests/test_beat_verify.py` replays the model's recorded answers.

## The shape

1. **A model reads the finished beat.** It answers one schema-constrained question:
   what does the narration say happened? Every slot is an enum the engine builds at call
   time:
   - `player_ends_at`: one of the places the engine knows, or "somewhere not listed";
   - `changed_hands`: an item from the pack, the props here or this turn's outcomes, or
     "something else"; from and to are refs, "the floor", "nobody" or "someone not
     listed";
   - `trades`: the item, the seller and buyer refs, and `settled`;
   - `harmed`: a ref, and `hurt`, `down` or `dead`;
   - `arrived` and `left`: a ref or "someone not listed";
   - `time_of_day`: night, before dawn, dawn, morning, midday, afternoon, dusk, evening,
     or "unstated".
2. **Code validates the answer.**
   - Every claim carries a `quote`. Code checks that the quote is the page's own
     narration, with speech blanked first, because a character may say anything.
   - The quote must be at least three words long.
   - Every slot must hold the engine's own value. A claim that fails is dropped.
   - A claim stated twice is kept once.
3. **Code compares the claims with the engine.** The engine's side is `resolution.outcomes`
   plus the scene after the turn (`beat_verify.facts_from`). A claim is judged only where
   the engine holds the fact outright. A thing "not listed", a newcomer, or a wound in a
   beat where nothing rolled harm is left alone.
   - **Contradiction:** the page claims what the engine did not do. It is repaired through
     `GMAgent._repair_sentences`: one targeted rewrite of the sentence with the engine's
     fact named, checked by reading the rewrite back. The backstop then cuts the sentence,
     and for a move or a sale puts the engine's own sentence on the page.
   - **Omission:** the engine did something the page never says. Only the trade is judged,
     and only when the page does not even name the thing. The backstop puts the engine's
     refusal before the hand-back.
4. **Each contradiction is asked once more** (`beat_verify.confirm`). It becomes a closed
   yes-or-no question about its one sentence, and is kept only on a yes. The hour is not
   asked again (see below).

## Prior art

A second pass checked every source against the primary paper or model card.

- **Wiseman, Shieber & Rush 2017**, "Challenges in Data-to-Document Generation", EMNLP
  (aclanthology D17-1239).
  - An information-extraction model reads the generated text into (entity, value, type)
    records, which are compared with the source records.
  - Relation generation (RG) is the precision and count of extracted records found in the
    source.
  - Content selection (CS) is precision and recall against the records extracted from the
    gold text.
  - Content ordering (CO) is a normalised Damerau-Levenshtein distance.
  - **The documented weakness:** their extractor scores over 90% accuracy, yet it recalls
    only about 60% of the relations. Run on human-written gold summaries, it scores 91.77%
    RG precision, so about 8% of its "errors" are its own.
  - This is why the bench below scores the READER (per-claim precision and recall)
    before it scores the alarms.
- **QAGS**, Wang, Cho & Lewis 2020, ACL (arXiv 2004.04228).
  - It generates questions from the output, answers them from both the source and the
    output, and compares the answers.
  - Pearson correlation with human judgement is 54.53 on CNN/DM and 17.49 on XSUM.
  - In their own error analysis of 400 XSUM cases, 8.75% of the questions were
    nonsensical and 32.5% of the source-side answers were wrong.
  - Here the source side is never read: the engine's records are the answers. Only the
    page side carries a reader's error.
- **The checker inherits its reader's errors.**
  - FRANK (Pagnoni et al. 2021, NAACL): every metric correlates weakly with human
    judgement (best 0.27 Pearson; QAGS 0.06), and the QA metrics correlate negatively on
    coreference and discourse errors.
  - SummaC (Laban et al. 2022, TACL): granularity decides the result. With the whole
    document as premise, an NLI model gave 0.91 entailment to a summary holding an
    unsupported sentence. That is one reason the second read here asks about **one
    sentence**.
- **LLM claim extraction and verification.**
  - FActScore (Min et al. 2023) splits text into atomic facts. Its automatic estimator is
    within 2% of human scores.
  - SAFE (Wei et al. 2024) agreed with humans on 72.0% of 16,011 facts and won 76 of 100
    disagreements.
  - RefChecker (Hu et al. 2024): claim triplets beat other granularities by 4-9 points.
    Extractor precision and recall were GPT-4 92.4/88.6, zero-shot Mistral-7B 82.2/68.2.
    Triplets cannot carry time qualifiers.
  - Claimify (Metropolitansky & Larson 2025) extracts nothing from a sentence it "cannot
    be disambiguated", and 99% of its claims are entailed by the source.
  - MiniCheck (Tang, Laban & Durrett 2024): a 770M checker reaches GPT-4's level on
    LLM-AggreFact. Claim decomposition showed "no clear indication" of helping.
  - **Taken here:**
    - typed, narrow slots;
    - abstention values ("not listed", "unstated");
    - a verify-each-claim step;
    - time scored on its own row, where FRANK and RefChecker both found it weakest.
- **Games.**
  - Callison-Burch et al. 2022 (EMNLP): a fine-tuned 64B model tracking D&D state
    reached 58% joint accuracy.
  - NCP-Bench (Ma et al. 2026, arXiv 2608.08160) audits narration against an "active fact
    ledger" with an LLM. All 4 of its disputed false positives in a human check of 100 were
    at state transitions.
  - No published work was found that reads typed claims out of game-master narration and
    compares them in code with engine outcome records. Wiseman's RG against box scores is
    the nearest.
- **Small structured-extraction models.** The vendor claims below were verified; there is
  no independent evaluation of either model.
  - **Osmosis-Structure-0.6B** is Qwen3-0.6B trained with RL on 500K synthetic examples.
    It is meant as a second pass that structures another model's free-form answer. Its
    only published results are math benchmarks; there is no benchmark for extraction from
    prose.
  - **NuExtract 2.0** has no Ollama build on this machine, so it was not measured.
- **Could not source:** JSONSchemaBench's numbers; FIREBALL's numbers beyond its abstract;
  how NuMind computes its F-score.

## Schema enforcement probe

Run 2026-10-03 on the real schema: 6 runs per model, the first at temperature 0 and the
rest at 0.7. The passage was built to tempt off-enum answers: a hammer not in the pack,
the street, a boy not listed.

| construct | gemma-4-12B | Osmosis-Structure-0.6B |
|---|---|---|
| required top-level keys | 6/6 | 6/6 |
| nested object, enum + required | 6/6 | 6/6 |
| array of objects, enum slots + required | 6/6 | 6/6 |
| boolean inside array items | 6/6 | 6/6 |
| `maxItems: 6` | 6/6 | 6/6 |

This matches memory `ollama-schema-enforcement`: required properties and enums hold.
Enforcement is not quality, though. Osmosis's answers were in-schema and wrong: invented
quotes, "someone not listed" for everybody, and `player_ends_at: the great square` for a
walk into the street. Its runs took 10-33 s, because it filled `num_predict` with repeated
rows.

## The bench

`tests/beat_verify/gold.py` holds 50 labelled beats.

- **36 tuned beats.** These come from the owner's 2026-10-03 save as played live (the
  `kesst:` and `talk:` sources) and from the Bobby corpus (`bobby:`). Their prose is cut
  to the sentences a label needs; the saves themselves are never committed. A beat marked
  "draft" is the text before a check repaired it: the flagged sentence from the save's
  `truth-checks` row put back. The set includes every case in the brief:
  - "You move toward the anvil";
  - "the smith, Korvu, … takes the crate from you";
  - "The transaction is finalized. The heavy clink of the coin";
  - "The clerk's eyes drop to the floor";
  - "midnight" and "the first hint of dawn" against the clock;
  - "You step out of the heat of the smithy and into … the street";
  - 24 clean beats that must raise nothing.
- **14 held-out beats.** These come from the scripted sessions of 2026-09-25
  (`tests/replay`). They were labelled before any run, and nothing was tuned on them.

Each beat carries:
- the engine's side, in the shape `facts_from` builds;
- what the narration claims, hand-labelled;
- the alarms a correct comparison raises.

`tools/beat_verify_bench.py` scores three things:
- the reader, per claim category;
- the alarms, per category, before and after the second read;
- the beat-level false-alarm rate on the clean beats.

It also runs the regex checks on the same beats. Their harness is a stub engine with the
same places, pack, clock and outcomes, plus `narration.contradicts_state`, the review's
state reader.

### Results, 2026-10-03

**gemma-4-12B (heretic), 2 runs over all 50 beats.**

Ollama was shared with lanes F and N throughout. An earlier run under heavier contention
had a read median of 8.4 s.

| claims (validated) | precision | recall | precision with no quote check |
|---|---|---|---|
| player ends at | 0.91 | 0.91 | 0.91 |
| changed hands | 0.67 | 0.88 | 0.61 |
| trades | **1.00** | **1.00** | 0.71 |
| harmed | 0.86 | 0.86 | 0.86 |
| time of day | 0.88 | 0.88 | 0.78 |
| all | 0.84 | 0.90 | — |

- The quote check made the difference on trades: "the exchange" and "the sound of a
  person who has finished their part in the exchange" both arrived as settled sales.
- Latency of the read: median 4.4 s, p90 6.1 s, max 14.7 s over 100 calls.
- Reads that failed: **0 of 100**. Across every gemma bench run this session it is
  0 of 244.

**The alarms against the regex checks.** Alarm counts are summed over the two runs for
gemma; the regex checks are deterministic and ran once.

| category | regex checks: P / R | read back, first read only: P / R | read back + second read: P / R |
|---|---|---|---|
| move | 1.00 / 1.00 (3/3) | 0.67 / 0.67 | 1.00 / 0.67 (4/6) |
| hands | 1.00 / 0.40 (2/5) | 0.80 / 0.80 | **1.00 / 0.80 (8/10)** |
| trade | 1.00 / 0.50 (2/4) | 1.00 / 1.00 | **1.00 / 1.00 (8/8)** |
| harm | 1.00 / 0.33 (1/3) | 1.00 / 0.33 | 1.00 / 0.33 (2/6) |
| hour | 1.00 / 1.00 (3/3) | 1.00 / 1.00 | **1.00 / 1.00 (6/6)** |
| all | 1.00 / 0.61 | 0.88 / 0.78 | **1.00 / 0.78** |
| clean beats falsely alarmed | 0 of 36 | 2 of 72 | **0 of 72** |
| bad beats fully caught | 7 of 14 | 20 of 28 | 20 of 28 |

The second read asked 24 of the 100 beats, at a median of 3.5 s and a max of 20.9 s. It
refuted both first-read false alarms and no true one:
- "You thrust the heavy crate forward across the workbench" as a hand-over;
- "the sudden, ringing silence of the square" as a move.

The regex checks' 0 false alarms are not free. Each was patched after a live false alarm
on these same beats (`refused_move` for the anvil, `contradicts_state` for the clerk's
eyes), and their misses are the phrasings nobody had patched yet:
- "Korvu takes the crate" with no "from you";
- "the transaction is finalized" on a turn with no `sell`;
- the crate lifted "from the dirt" that the engine never picked up.

**Osmosis-Structure-0.6B, 1 run over all 50 beats.** This ran an earlier build of the
module: before the bench's last fixes (each sentence judged, descriptor names, "left
behind", the pick-up demonstration).
- Claims: precision **0.06**, recall **0.16**.
- 242 claims were dropped by validation, mostly quotes that are not on the page.
- 11 of 50 reads did not parse (22%). It runs to its token limit repeating rows.
- Alarms before the second read: P 0.27, R 0.20, and 6 of 28 clean beats falsely alarmed.
- Read latency: median 3.7 s.

It is a model for re-shaping another model's answer, which is what its card says. It is
not a reader of prose, and it is not used.

**NuExtract 2.0** has no Ollama build on this machine, so it was not measured.

**The pick: gemma-4-12B, the narrator's own model.** The check routes to the narrator's
model and host (`BeatContext.reader`), so it costs no second model in memory.

### What the reader still gets wrong

- **"You are standing where the paths diverge"** (bobby:6) is read as staying at the way
  in, both runs. This is why `refused_move` stays.
- **Held-out harm.** When the player swings at a Commoner and misses, and the page has
  "the man" hit the ground, the reader puts the blow on the man in stained leather, who is
  already down. A hurt claim against a body already down is not judged, so no alarm is
  raised. The regex checks miss both of these beats too.
- **"the pre-dawn gloom" at 01:28** is read as "dawn". The alarm is right either way:
  neither word fits that hour.
- **Hands over-reports.** "He takes the paper back from you" and "closes his hand around
  one of the shards" come back as "something else". Things with no engine name are never
  judged, so these cost nothing.

### The second read, and what it was not allowed to do

The first wording of the questions refused true alarms.
- With "Answer no unless the sentence plainly says it", gemma refused 3 of 5 true
  contradictions on a probe, "The transaction is finalized." among them.
- "Does the crate pass from you to the smith?" was refused for "Korvu takes the crate":
  the sentence never says "from you".

The questions now ask only whether the thing moved; the first read supplies the
direction. The hour is not asked again: "is it dawn now?" of "the pre-dawn light" is
correctly answered no, and that is still a true alarm at 01:28.

## Retired, and what stays

Retired where the round trip measured at least as good, at equal precision:

| check | category | regex | read back |
|---|---|---|---|
| `thing_kept` | hands | R 0.40 | R 0.80 |
| `trade_claimed` | trade | R 0.50 | R 1.00 |
| `time_of_day` | hour | R 1.00 | R 1.00, no false alarm |

Kept:
- **`refused_move`** measured better (3/3 against 4/6). Both run. On one sentence the
  heavier finding wins, and the read back goes first at equal weight.
- **`empty_roll`** is equal on harm. It is also the only reader of a victim who is not on
  the actor list ("Dagan Havenstone", G2), a claim this member never judges.
- **Every other check.** The bench has no row for its kind: road, direction, route,
  bearing, land, faces, speech, keepers, hooks, size, and the rest. Those are the
  next rows to label before anything else retires. (Setting has rows since 2026-10-16;
  see "The kind of place" below, and `setting_kind` still runs.)

`time_of_day`'s repair cost no model call: it swapped the clock's word in. Its
replacement costs the read, plus at most one rewrite of the sentence, and the backstop
cuts. That is a real cost, accepted because the old repair was itself an English reader.

## When the read fails

`beat_verified.find` raises. The registry books a `check-error` row for the member, and
the turn goes on with every other check. On that beat, nothing stands in for the three
retired categories; the brief allowed this, and it is said here plainly.
- Measured on the bench: 0 of 244 gemma reads failed.
- Osmosis failed 11 of 50.

Every live read is logged as a `beat-verify` row in the turn log: claims, dropped claims,
seconds, and the error if there was one. The live failure rate can be read off saves.

## Not done

- Not played live in the running app. The member is proven through `_repair_sentences`
  and `_groom` with scripted replies, and on the bench with the real model.
- The interface for lane N's beat reader is `facts_from` / `read` / `diff`. Folding this
  read into that call is for after lane N merges; whether one call answering both does
  worse than two must be measured, not assumed.
- Omissions are judged for trades only.
- `arrived` and `left` are read, but only a `left` of somebody the engine keeps here is
  judged, and the bench has a single `left` claim. That is too few to say anything.
- The regex checks without a bench row remain English readers.

## The people not here (2026-10-09)

docs/narrator-after-defeat.md has the defect and the runs. The reader had no code for
anybody the engine holds elsewhere, so the raiders who had robbed the player and gone,
written lunging at the wagon an hour later, were "someone not listed" and never judged.

- The people held elsewhere in town (`beat_reader.away_people`) are offered as codes,
  marked "not here" (`Person.here`).
- On a beat with anybody away, and only then, the reader is asked `shown_here`: which of
  them the passage shows here and now. A beat with nobody away is asked word for word
  what it was asked before (all 50 earlier bench beats: identical messages and schema).
- An away person shown here, hurt here, or arriving with no arrival the engine made is an
  `absent` contradiction (`beat-absent`, weight 3). Its second read asks WHO the
  sentence shows, from the codes, and compares in code.
- Bench, 2 runs, 55 beats: `absent` P 1.00 R 5/6; clean beats falsely alarmed 0 of 76;
  every earlier category as on master. An `attacks` slot was tried and taken out: it cost
  harm claims 12/14 → 8/14 on the same beats.

## Somebody here, written gone (2026-10-09)

docs/departed-beast-and-species-name.md has the defect and the runs: a creature the engine
kept on its seam, written *"The Aelzeldra is gone."* while the player slept.

- The `left` slot read it — once the readers were told what the creature is
  (`mentions.what_they_are`: told "human", 0 of 3 reads found a departure; told "monstrous
  humanoid", 3 of 3).
- The second read refused it: *"does this sentence say that Aelzeldra goes out of the
  place?"* was answered no 3 of 3. It asks *"…has gone — left, or no longer here?"* now
  (`question`), probed against both a departure told as a state and one told as an act.
- The `absent` second read (`_shows`) lists the people as the first read does — what they
  are, and "not here" — not by name alone: a goblin standing here was the away "goblin
  with a scarred cheek" 16 of 16 by name, 2 of 16 so.
- The `left` line of the instruction says "or whom it says is no longer there": on our own
  server, the fixed branch's first live rest turn wrote "the beast is no longer within
  your immediate sight" and the reader filed it as an hour (dropped). With the line it is
  read as a departure 2 of 2 on the bench, and the second read refuses it 2 of 2 — out of
  sight is not quite gone, and the engine holds the creature "far"; labelled either way.
- Bench, 2 runs, 59 beats: `presence` R 2/2, `absent` R 6/6, clean beats falsely alarmed 0
  of 82; every other category as on master.

## The body's conditions (2026-10-16)

The owner's wife's market brawl on 0.2.19 (free narrator, gemma-4-12B): "it was unclear
if the user was grappled or if the narration just described it that way and the latter
shouldn't happen." The engine grappled nobody; three beats put a woman's fingers round the
player's throat. The English reader of the day (gm/state_claims.py) had no grappled row,
and its one hit in that fight was a false "prone" on an aim ("aiming to knock you off your
feet"), which cut the creature's wind-up down to its filler.

- **The question.** On a fight's beats (`Facts.bodies`: a fight on, or a blow, spell or
  manoeuvre resolved), the reader is asked which bodies the narrator says ARE held or
  impaired at the end of the passage: `CONDITIONS` (grappled, pinned, prone, entangled,
  stunned, dazed, blinded, deafened, paralyzed), keys of `states.TAGS`, each quoted.
- **The judgement, in code.** `_condition_unheld`: somebody here and on their feet, the
  engine holding no such state on them (`Person.holds`, asked by tag through `has_state`),
  and no effect this turn naming that condition for that body. A "pin" inside a grapple
  the engine made is the narrator's degree, not a hold from nowhere.
- **The second read asks whom** (`_in_condition`, the `_shows` shape): asked yes-or-no,
  "his weight pins yours against the shattered furniture" kept a pin on a bystander.
- **Repair** is `beat-condition` (weight 3) through `_repair_sentences`; the backstop cuts.
  `state_claims`' body question stands down wherever this is asked (`asks_bodies`), except
  on sentences written after the read (`unread`).

**A call of its own, not a slot.** Folded into the first read, the conditions read well
and cost `harmed`, three wordings running (22 fight beats of the bench, gemma x2, Ollama
shared with live audits):

| version | harm claims | harm alarms kept | condition alarms | clean beats alarmed |
|---|---|---|---|---|
| master (no conditions) | 15/19 (P 0.79) | 3/6 | 0/8 | 2/29 |
| slot + missed-grab demo + "never an attempt…" | 7/19 | — | — | — |
| slot, no demo | 7/19 (P 0.70) | 0/5 | 5/8 | 2/30 |
| slot, short clause ending on harm | 16/20 (P 0.73) | 0/6 | 6/8 | 2/30 |
| **separate call (shipped)** | **16/20 (P 0.80)** | **2/6** | **4/8, P 1.00** | **2/30** |

The two clean-beat alarms are the same harm alarm master raises (ho-pinioned-strikes). The
first read's messages and schema are now byte-identical to master's on every beat (49
non-fight and 22 fight gold beats compared in code); the bodies call is extra, on fight
beats only: read latency median 8.9 s for both calls on the recordings below.

**On recorded beats.** The committed fight recordings (tests/replay/*fight*, 99 fight
beats, each against the scene after its own turn): `state_claims`' body question raised 0
alarms; the read back raised 2, the second read kept 1 — "The fallen man in tattered gear
lies crumpled in the dirt", of a standing bystander the engine itself had named "fallen
man". Defensible either way; no clearly false alarm. On the report's own beats (replayed
offline, scratch only): the regex caught 0 of the 2 invented grips and raised 1 false
prone; the read back caught 2 of 2, both kept, and claimed nothing on the aim or on the
first grab ("reaching out to grab you by the throat", an attempt).

**Misses.** "Her fingers tighten around your throat as she leans in close" (0/2 on the
bench, though the report's own wording of it was caught) and an invented "momentarily
stunned" (0/2). Recall on condition alarms is 4/8; the precision is what was bought.

## Gifts by the floor, deals nobody made, and the attempts (2026-10-16)

Live on 0.2.20's code (a scratch save; free narrator, gemma-4-12B): the player helped the
smith lift his cart and asked for fair pay. The engine rolled both. The help failed, the
smith lifted it alone, and the request failed ("the smith says no and pays nothing:
nothing changes hands"). The page then had him toss "a piece of coarse, stained leather
… into the dirt between you. 'There's your pay.'" and ended "You are still here, and the
trade is finished.", which a repair turned into "…the trade is not finished."

**The gift by the floor.** The read back heard the toss (`something else`, c4 -> the
floor) and skipped it: only an unlisted thing handed INTO the player's hands was judged.
Now an unlisted thing that a listed person here parts with to the floor or to nobody is a
`hands` contradiction (`_parts_with_unlisted`). It is judged only when nothing came into
the player's hands this turn and no resolved effect moved anything of that person's. Whether
the thing is given FOR the player, or is just the smith setting his own hammer down, is the
second read's question (`question`), not code's. A crow's feather is from nobody listed.

**The deal nobody made.** A settled sale of `something else` is judged only when a `sell`,
`buy` or `haggle` is on this turn's record. A thing the engine names is still judged with
no trade op: the crate still in the pack is not sold (kesst:18).

**The attempts.** Nothing compared the page with a check's verdict. The claims scrubber
(rules/intents.py) is English regex and backs any success claim once the turn has any
verdict. Prior art: the same split (the engine rolls, a model narrates) produced this
defect in agentic-dm-engine (issue #34: a death save narrated "passed" under a "fail"
badge). The one repair found in the open, infinite-realms-app PR #345, reads "you
succeed" and "you manage to" by regex and took four rounds of narrowing against false
alarms.

- `attempts_of`: every check and save this turn settled (`_ATTEMPT_OPS`, a whitelist).
  Each attempt carries who made it (the new `Outcome.actor`, stamped in
  `Engine._resolve_one`), the roll's own label and the intent's `because`. Aid Another
  counts as two attempts: the helper's, and the helped person's own effort. A request's
  label names who it was made of. Attacks are left to the blow lane.
- A call of its own (`attempts_messages`/`attempts_schema`) asks, per attempt, for
  `succeeds`, `fails` or `unsure`, as a required enum with a quote. `unsure` is no claim.
  The quote may be speech: a refusal is often only said aloud.
- Code compares the answer with the verdict. A mismatch is `beat-attempt` (weight 3),
  repaired through `_repair_sentences` with the verdict as the fact (no number). The
  second read asks whether the sentence shows the attempt working or failing.

**Its own call, measured.** One run on the bench. Every beat with no check of its own was
given one unrelated attempt, so that the folded slot was shown everywhere, as the bodies
lane measured `conditions`.

| version | attempt claims | other slots | clean beats alarmed |
|---|---|---|---|
| folded into the first read | P 0.94 R 0.97 | `shown` 5/5 -> 2/5, `absent` alarms 3/3 -> 2/3, trade alarms 4/4 -> 3/4, harm claims 9 -> 8 of 11 | 2/73 |
| **separate call (shipped)** | P 1.00 R 1.00 on the labelled beats | first read byte-identical (tested) | 1/73 |

The separate call had its own weakness: given an unrelated FAILED check, it described the
scene in view as the check succeeding. On a failed "Perception check: the player looks
about" it did so on 20-22 of 71 beats, and the second read kept 3-4. One line ("a
description of what is there to be seen is not a search or a look succeeding") and a third
demonstration that tells neither attempt brought that to 3-5 of 71 claimed and 1-2 kept,
with Disable Device, Survival and Sense Motive at 0-2 claimed and 0-1 kept. The labelled
gold was unchanged (32 of 32 claims, 11 of 11 alarms). Tried and dropped: a second read
asking WHICH attempt a sentence tells (the `_shows` shape). It kept 5 of 5 unrelated
Perception claims, worse than yes-or-no.

**Bench, gemma-4-12B x2, 108 beats (41 new).** Ollama was shared with other lanes. The
read median was 4.7 s and the max 23.2 s across the three calls.

| | master's code, same gold (x1) | this branch (x2) |
|---|---|---|
| attempt claims | none read | P 1.00 R 1.00 (64/64) |
| attempt alarms | 0/11 | **P 1.00 R 1.00 (22/22)** |
| hands alarms | P 1.00 R 0.50 (4/8) | P 1.00 R 0.88 (14/16) |
| trade alarms | P 0.67 (2 false: the live "trade is finished", and its twin) | **P 1.00 R 1.00 (8/8)** |
| clean beats falsely alarmed | 2/73 | 2/146 (both ho-pinioned-strikes, harm, as on master) |

The scenery beats (a crow's feather, the smith's hammer on the anvil, a nail tossed on the
scrap heap) raised nothing in either run: the second read refuted the hammer and the nail
both times. One miss across five runs: the second read refuted "drops it in the dust at your feet"
once.

**On recorded beats.** The committed recordings (tests/replay, 169 GM beats, each against
the scene after its own turn; their outcomes predate the stamp, so `actor` was filled from
the turn's own intents): 24 beats had an attempt. The first read raised 2 attempt alarms,
a creature lunging "to grab the intruder" and a crowd that "struggle to clear the path",
both read as the player's stolen-satchel check failing. The second read refuted both, so
0 were kept. It raised no gift-by-the-floor alarm and spared no trade claim.

**Left alone:** a hosted provider's reads are unmeasured; a turn log written before the
stamp has no `actor`, so its attempts are not asked about; spell and creature-ability saves
inside a `cast` or `use_ability` outcome are not separate outcomes, so they are not
listed yet.

## The kind of place (2026-10-16)

A real player's 0.2.19 market fight (free narrator, gemma-4-12B): "The heavy weapon
whistles through the air… thudding uselessly into the wooden planks of the deck." There is
no deck in a market. The only reader of a setting was `gm/checks/setting_kind.py`, a word
list of a tavern's and a room's furniture, which the owner's direction says must not grow.

- **The vocabulary.** `places.SETTINGS`: a town street, square or market; inside a
  building; a tavern or inn; open country; underground; aboard a ship or boat. The kinds a
  place truly is come from `places.settings_for`: the ground in the id, the floor plan's
  roof, the side of the settlement's edge and the kind words. Diku's sector type is the
  precedent: one kind per room from a short fixed list. It is generous where a place is
  generous. A cellar is a room and a vault. The way in and the gate are road and town. A
  graveyard is street and open ground. A ship counts only where the place stands on water.
- **The question.** A call of its own (`setting_messages`), one entry per sentence, for
  the hour's reason: the deck was one sentence among a market's. The reader is not told
  where the engine holds the party. Asked only where `Facts.settings` is known: the union
  of where the beat began, where it ends and every place its walk passed through.
- **The judgement, in code.** `_setting_wrong`: a kind not among the place's kinds is a
  `beat-setting` contradiction (weight 3). It is not judged when the sentence names the
  place the engine holds. The second read asks whether the scene is set in that kind of
  place, not somewhere only seen in the distance or from outside. Probed: 10/10 on the
  tuned sentences, 12/13 with the recordings' own false alarms added. Two other wordings
  scored 9/10.
- **Repair** goes through `_repair_sentences`. The backstop cuts the sentence.

**A call of its own, measured.** Gold beats: 12 labelled for setting, 6 of them bad. Full
bench, every beat, gemma x2, with Ollama shared with live play and other lanes:

| version | setting alarms kept (beats) | clean beats falsely alarmed | other categories |
|---|---|---|---|
| slot of the first read | 12/12, 5 false | 5/110 | `shown` claims 10/10 -> 4/10, `absent` alarms 6/6 -> 4/6, harm claims 17 -> 15 |
| own call, first prompt | 10/10, 18 false | 8/112 | identical first read |
| own call, shipped prompt (setting call only) | 12/12, 0 false | 0/152 | first read byte-identical to master |

- The shipped prompt demonstrates a weak cue that is not reported: dirt, a table, the
  ground. On the first prompt, 8 of the 18 false alarms were things any place has.
- The other 10 false alarms were fixed in code:
  - a walk's places joined the union (counter-and-go);
  - the way in became road as well as town (gates-receive);
  - a taproom beat already in the bench was relabelled as a true alarm (man-on-the-stool).
- The setting call costs a median of 2.5 s and a p90 of 4.1 s over 166 calls, contended.

**On recorded beats** (tests/replay, held out, 232 drafts judged against the engine's
place before and after each turn):
- 62 drafts alarmed on the first read, 47 after the second. By hand: about 36 are true against the engine of the day, 7 are false, and 4 are walks the recording does not hold.
- Most kept alarms are true against the engine of the day: the 2026-09-25 scripts where a
  walk "into the worst tavern" left the party at the west crossing, the town script held
  in the wild while the prose walked its streets, and rooms and halls furnished at a
  street crossing.
- The false ones: a smith at work written as a forge interior while the engine held the
  market (5 drafts), "display racks" (1), and "the muddy rut of the road" in town (1).

**Kept beside it:** `setting_kind.py`. On its own measured rows (talk:0, talk:4,
man-on-the-stool) the read back caught every beat both runs at no cost. It is a candidate
for retirement under this doc's rule, but it was not retired in this lane.

## Scenery that changes state (2026-10-16)

The same fight: "the blade… clattering against a clay pot… the pot shatters into shards".
Then "a heavy wooden crate sits partially overturned, its contents of iron nails…". Then
"I grab a shard of the broken pot and stab him". The shard was minted (the world never ran
out) and swung, because an improvised attack took any `params.item`.

**Decided, with the sources** (gm/scenery.py's docstring cites them):
- The narrator may describe scenery. That is the look-only tier: Inform's scenery and
  backdrops, TADS 3's `Decoration`, Diku's extra descriptions.
- The narrator may not change scenery's state. Fate: "the barn doesn't catch On Fire!
  without someone kicking over the lantern."
- What the narration showed is established and usable, as Fate's "poorly lit" is.
- A detail that follows from the place is free. A stretch is not. Fate Condensed revised
  its charge to exactly this in its 2020 changelog.

**Built.**
- `Engine._picked_from_nowhere` refuses a pick-up with no record.
- `Engine._improvised_unheld` refuses an improvised weapon not in hand or on the ledger.
  It is asked before any fight opens.
- `gm/scenery.py` asks one closed question per unrecorded thing the plan reaches for:
  shown here (quoted, the quote checked to be the narration), commonplace here, or not
  here. A shown or commonplace thing is ledgered through `place_prop` with its `origin`.
  This is "seen people are real" for things, applied at first use rather than first
  mention, so no beat pays a call for it.
- A fight's Steal of a thing lying on the ground becomes the pick-up it is.
- `_taken_though_refused`: on a turn the engine refused a pick-up as not there, the page
  showing the player taking it is a `hands` contradiction.

**Measured.**
- Tuned probe: 24/24.
- Held out: 18/24, with no false ledgering. The misses are an apple from a smashed crate
  ledgered as commonplace rather than shown, a torch in its bracket and a thrown bucket
  refused (2 cases, twice each).

**Live** (scratch copy of hv-data, Khalmorin market, gemma-4-12B, contended):
- "I grab a shard of the broken pot and stab him" with no pot: scenery "not here". The give
  was refused: "There is no shard here for Kesst Vayr to pick up". The plan's attack was
  unarmed. Nothing was minted.
- The prose still wrote "The shard bites deep into the soft tissue of his shoulder" against
  an unarmed strike's tell. No reader judges which weapon a blow was struck with.
- "I hurl the heavy iron kettle at Lyraea", a kettle the previous beat put on the stall:
  shown here, ledgered `origin: narrated`, thrown at -4 with Dex, missed 4 against AC 14,
  and "The heavy iron kettle lies where it fell."

**Not built.**
- A read-back question for a narrated state change (the pot shattering itself). With the
  engine hole closed, a broken thing is only usable if the player read it broken.
- Ownership of narrated scenery (a pot on a stall is the stall-keeper's).
- Ledgering at first mention.

### Refusals biased toward allowing (2026-10-17)

A wrong refusal breaks play harder than the old minting did: the player read about the
torch and is told there is none.

- **Why the first held-out misses failed.** The torch and the bucket were the model's own
  answer, "not here" with no quote. The quote check played no part. The apple was ledgered
  as commonplace, so it was not refused. The live crate was the window: six transcript
  entries no longer reached the arrival beat.
- **What changed.**
  - A refusal must name its reason: a piece of something no passage shows broken; taken
    away, gone, far off, or only spoken of; or would not be found in a place like this.
  - The reader is told the place's kinds from `settings_for`.
  - A "shown" answer whose quote misses is ledgered as fitting, not refused.
  - A "never shown" or "piece of something" refusal is overruled when every word of the
    player's name for the thing is in the narration, with speech blanked. "Gone" refusals
    are never overruled.
- **What was tried and dropped.** A narrow yes/no second read. Asked about "the bucket",
  gemma answered "no" while writing "At your feet" as where it was. The best of three
  wordings scored 6/8.
- **Held-out sets, gemma x2, contended:**

  | set (here/absent) | written | false refusals | false ledgering |
  |---|---|---|---|
  | 1 (22/22) | before the redesign, then used in tuning | 2/44 (the bucket) | 0/44 |
  | 2 (8/8) | after the override, used in rewording | 0/16 | 0/16 |
  | 3 (8/8) | before the final run, never tuned on | 0/16 | 0/16 |

  - Before the rewording, sets 1 and 2 gave 0 false refusals and 4 false ledgerings. A
    taken-away apple and boathooks were filed as "broken" and then overruled.
  - The old design on set 1 gave 2/44 false refusals and 0/44 false ledgering.
  - The bucket ("hurls a bucket of eel water at your feet") is still refused, now as
    "gone". The sentence is ambiguous, and it is the one known miss.

## What the player's blows were struck with (2026-10-17)

The live shard turn: the engine refused the shard and rolled an unarmed strike, and the
page wrote "The shard bites deep into the soft tissue of his shoulder."

- **The question.** A call of its own (`swing_messages`), asked only on a beat where the
  player struck. Those are the attack outcomes with blows on a roll made at
  `visibility: player`. The codes are the PC's carried weapons, `unarmed strike`, the
  weapon the engine swung, `something else` and `not shown`.
- **The judgement, in code.** `_weapon_wrong` compares the answer with
  `Outcome.blows[...]["weapon"]` and raises `beat-struck-with` (weight 3). `not shown` is
  never judged. The second read (`_struck_with`) asks which weapon the sentence shows,
  from the same codes, and keeps the alarm only for a weapon that is neither the engine's
  nor `not shown`.
- **Slot or call, first prompt, 16 beats x2:**

  | version | weapon alarms before / after second read | read latency (median) |
  |---|---|---|
  | own call | 12/14, 2 false / 12/14, 2 false | 9.3 s |
  | slot of the first read | 13/14, 6 false / 13/14, 2 false | 12.3 s |

  The slot also changes the first read on every beat with a blow. The call of its own
  leaves the first read byte-identical, so the call was kept.
- **Shipped prompt, 25 beats x2 (8 held out).**
  - Weapon claims: precision 0.95, recall 0.95.
  - Alarms: 20/22 caught, 0 false, 0 of 26 clean beat-runs alarmed.
  - The 8 held-out beats were correct both runs.
  - The two misses are a shortened paraphrase of the shard beat. The verbatim live beat is
    caught 2/2 and confirmed.
  - The demonstrations were changed after the first run: a weapon named in its own
    sentence, and a hilt counting as the weapon. The pommel false alarm went with them.
  - Read latency had a median of 30 s. Ollama was heavily contended.
- **The dice popup.** Over a blow, the subtitle is now the engine's words (`_roll_why`:
  "Kesst Vayr against Lyraea"), not the plan's `because`. A reaction keeps its own reason,
  which the engine wrote.

**Live, 2026-10-17** (scratch copy, Khalmorin market, fight with Lyraea, contended):
- "I grab a shard of the broken pot and stab Lyraea with it":
  - The scenery read answered "not here: a piece of something no passage shows broken".
    The give was refused.
  - The plan's attack was the rapier. The popup read "Attack with rapier / Kesst Vayr
    against Lyraea". The roll was 13 against AC 14, a miss.
  - The draft wrote "…the shard … as you lunged, it bit deep into her shoulder". The harm
    repair turned it into a graze. The struck-with read then found `something else`
    against the rapier and cut the sentence. The blow backstop put "Your attack with the
    rapier misses Lyraea." on the page.
  - Still shipped: "the force of the impact sends her stumbling back" on a miss. No
    reader claimed it.
- At the gate, "I take a torch from its bracket on the gatehouse wall": no passage had
  shown a torch. The reader answered "fits a place like this". It was ledgered
  `commonplace` and the tell was "Kesst Vayr takes the torch." The narrated-and-shown path
  was proved live with the kettle the day before.

## A blow before the dice, and a fighter nobody holds (2026-10-17)

Live on the integration branch (free narrator, gemma-4-12B, the inn fight), two beats the
read back passed.

**A blow landed on the turn the fight was only joined.** "Draw my dagger and stab the one
behind the bar" joined battle and rolled nothing. The page shipped "He bellows, a raw sound
of defiance, and recoils from your strike". The claims scrubber had cut the stab sentence;
`swing-not-yet-struck` (regex) has no "recoils"; the harm repair turned "pain" into
"defiance", and the re-read of that one sentence, read alone, named "someone not listed",
which is never judged. Read whole, the shipped beat claimed no harm at all.

- `Facts.joined`: the player's attack this beat resolved as `battle_joined` with no roll.
  The struck-with question (`swing_messages`) is asked on such a beat too.
- `_struck_early`: any blow of the player's it finds (any weapon, "not shown" included) is
  an `early` contradiction, `beat-swing-early` (weight 3). The second read asks whether the
  blow already ARRIVED — "not only drawn, raised, aimed, or still coming".
- The backstop cuts the sentence and puts the joined tell before the hand-back.
- **Measured**, gemma-4-12B x2, on 37 joined-turn texts (19 shipped beats from the scratch
  saves, 18 drafts from tests/replay; one had a rolled blow and was not asked):
  - first-read alarms on 7 clean beats' wind-ups ("You lunge forward, your fist aimed
    directly at the guard's face", "You draw your rapier and strike at the cutpurse"): all
    14 asks refuted by the second read, so no clean beat lost a sentence;
  - the 9 beats that name a blow of the player's landing were all kept, 2 of 2 each but the
    evidence beat (1 of 2 read whole; 1 of 1 as the rewritten sentence alone). In one of
    them the kept sentence was "your knuckles stinging", not the "force of your blow" before
    it;
  - also kept: a narrated MISS on a joined turn ("passes harmlessly past"), which the engine
    did not roll either;
  - missed: three beats whose landing is told only by the victim ("He staggers…", "collapses
    against the bar") with no blow of the player's named.

**A fighter the engine does not hold.** The same fight's next beat: "The other man… hesitates
for a heartbeat before lunging toward you, his hands out like claws." The read back ran on
that beat and claimed nothing of him: its vocabulary judges people it has a code for, and the
`attacks` slot that might have was taken out (harm 12/14 -> 8/14). The beat reader read him
as a newcomer here; the aftermath rightly made no body in a fight.

- `gm/checks/phantom_fighter.py`: in a fight, a beat-reader mention answered "new" and here,
  or given to somebody held elsewhere in town, is asked one closed question about its
  sentence: does it show them fighting — "themselves attacking … not only being attacked or
  grabbed, watching, shouting, flinching, backing away, fleeing or standing by"? A yes cuts
  the sentence (`fighter-not-in-fight`, weight 3, cut only).
- **Measured**, gemma-4-12B, on tests/replay's fight files (144 narrated texts, every one
  treated as a fight): 22 sentences asked, 2 kept — "A local laborer lunges forward … as he
  prepares to strike you" and "A desperate stranger lunges toward him", both people the
  engine did not hold at that turn (checked against the recording's scene). 0 false cuts.
  The first wording kept "it lunges forward to grab the intruder" as the INTRUDER fighting
  (2/2); "themselves" and "being attacked or grabbed" took it to 0/2. The live lunge: 3/3 on
  the draft, 2/3 on the polished beat (once the reader called him the away guard, which is
  why away mentions are asked too).

**Live, round by round** (scratch copy of the evidence save, combat panel: chip, Strike,
Commit turn, Roll):
- Round 2: tell "Kesst Vayr hits the one behind the bar with the dagger for 2 piercing." The
  draft brought in a man and a figure and repeated nine earlier sentences; what survived the
  cuts was the blow pass's line, "You strike the one behind the bar with the dagger for 2
  piercing." The creature's turn (the sap, a miss, 7 against AC 15) was written as a crossbow.
- Round 3: the same blow, 2 piercing. The beat had "You have him momentarily stunned by the
  pain", which the condition read caught and repaired to "reeling". The creature's miss (8
  against AC 15) was told as the sap that "fails to connect".

**Left:** the creature turn's weapon is not read (the struck-with question asks about the
player's blows only), and the crossbow invented in round 2 was carried into round 3's beat.
A blow told only by the victim's reaction on a joined turn is not claimed. The joined turn
was not replayed live (the fight was already on); it is proved offline on the evidence beat.
