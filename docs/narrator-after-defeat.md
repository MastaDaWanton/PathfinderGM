# After the defeat: the raiders do not come back on the page

*Design record, 2026-10-09. Branch `fix/narrator-after-defeat`. The code is
`play/views.py` (the downed door's `moved_on` lines, `_gone_since_narrated`),
`gm/narration.py` (`since_narrated`), `gm/prompts.py` (`call_prose_messages(since=…)`,
`scene_now(gone=…)`), `gm/beat_verify.py` (the away people, `shown_here`, the `absent`
contradiction and its second read), `gm/checks/beat_verified.py` (`beat-absent`),
`gm/beat_reader.py` (`Reading.struck`), `gm/agent.py` (what the guards struck),
`play/aftermath/seen_people.py`, `gm/judgement.py` (`embody_seen`) and `rules/engine.py`
(`Engine.walk_in`). The tests are `tests/test_narrator_after_defeat.py`; the bench rows
are the `defeat-*` beats of `tests/beat_verify/gold.py`.*

## The report

The skull-enemy lane, three runs on gemma-4-12B heretic in the caravan ambush
(`road-caravan-attack`): the player went down, the winners robbed them and went
(`rules/defeat.py`), and the next Continue narrated the raiders still swinging at the
player — once with a shield the player does not own — and that beat made new bystanders
through the beat reader. The owner: *"fix this before we cut a release"*.

## Reproduced

A scratch data root, a fresh dwarf fighter (Con 7, no weapon) in the caravan ambush,
punching the nearest raider until he fell (two turns), the save copied at that moment.
Each replay restores the copy, presses Continue (the downed door: the bleed, the hour,
the robbery, "The raider and the second raider have gone.", the quest) and Continue
again — the narrated beat being measured. Every model call was logged by a wrapper
around `gm.client.chat`, so the prompt the narrator was shown is on file.

**What the narrator was shown** on that beat (the before run's own prompt):

- "What you narrated just before this — the scene as it stands, which you are continuing,
  not restarting:" followed by the fight: *"The raider is closing the distance, his
  rapier gripped in his hand. What do you do?"*;
- the Continue line: *"… let the people and the place here go on doing what they were
  doing"*;
- "The engine decided nothing mechanical this turn.";
- a scene block with only *"friendly towards the player: Vyraxys Vexarion"*.

**Not one word** of the downed door: not the hour, not the robbery, not who went. Its
lines are transcript beats of kind `consequence`, and `narration.own_prose` keeps every
engine line out of "what you narrated" on purpose (docs/narrator-guards.md D4: an
engine sentence shown back as the model's own is a template taught). Nothing else
carried them. The model was told the fight was the scene, and that the people in it
should go on doing what they were doing. It did.

## Prior art

- **Inform 7** (Recipe Book §4.4, "Scene Changes", <https://ganelson.github.io/inform-website/book/RB_4_4.html>):
  a scene that ends moves what leaves it to "nowhere", and the next scene's description
  is produced from where things are now — off-stage things are not in it. The scene
  change is announced, not left for the next description to discover.
- **NCP-Bench** (Ma et al. 2026, <https://arxiv.org/html/2608.08160>), the long-horizon
  consistency benchmark already cited in docs/beat-verify.md: fact conflicts are the
  dominant failure (40–68% across models), and memory-augmented prompting cut commitment
  conflicts (26% → 4%) while fact conflicts persisted; an LLM auditor against a fact
  ledger correlated 0.96–0.99 across auditor models. Read here as: fix the input, and
  still audit the output against the engine's ledger — neither alone.
- Could not source: any published measurement of an LLM narrator bringing back characters
  the game state had removed. The before counts below are ours.

## What was built

1. **The input** (`views` → `narration.since_narrated` → `prompts.call_prose_messages`).
   The downed door marks its lines `moved_on`: the scene was carried on there with no
   narrated beat. The next prose call is shown them after the earlier beats, under
   *"SINCE THEN (the engine's own lines, already read by the player — do not repeat
   them; the scene stands HERE now, and goes on from this)"*, and the earlier beats are
   called *"the scene as it was then"*. The scene block, last in the prompt, says
   *"GONE from here since the last passage, and taking no part in this one: the raider,
   the second raider"* — from the engine's own `left` records on the turn log after the
   last `prose` row (`_gone_since_narrated`), on the beat after they went and never as a
   standing line. Only beats a door marks `moved_on` are shown, not every consequence
   beat: award lines and tells after a narrated beat are that beat's.
2. **The check** (`gm/beat_verify.py`, the round trip that already compared the page with
   the engine). It had no code for anybody not here — the departed raiders were "someone
   not listed", never judged — and the lunges at an axle hurt nobody and arrived nowhere.
   Now the people the engine holds elsewhere in town (`beat_reader.away_people`, the
   beat reader's own list) are offered as codes marked "not here", and on a beat where
   anybody is away the reader is asked one more closed question, `shown_here`: which of
   them the passage shows here and now, doing or saying anything. Code judges it: an
   away person shown here, hurt here, or arriving with no arrival the engine made is an
   `absent` contradiction (`beat-absent`, weight 3), repaired by one targeted rewrite
   with the fact named, then cut by the backstop. The second read asks **who** the
   sentence shows, from the codes, and compares in code — the yes-or-no question
   ("Does this sentence show the raider here…?") answered yes to *"Vyraxys is busy at
   the front, his voice now low and raspy"* twice of twice on the first live run.
3. **The bodies.** The beat reader reads the draft *before* the narrator checks
   (`GMAgent._groom`), and `seen_people` made people from that reading — including from
   sentences the checks then rewrote or cut. Now `Reading.struck` holds the read
   sentences the guards took off the page (the truth pass, the dead-men cut, the
   phantom-opposition cut), and a newcomer or an arrival who stood only in those is
   nobody. And `Engine.walk_in`, the one door the page's people come through, refuses
   anybody hostile to the player on the attitude track: a foe comes back through the
   engine's own doors (an encounter, `defeat.settle` when their hideout exists), never on
   the prose's word — whether the reader named them (`arrived`) or the words matched
   their name (`embody_seen`'s `_held_elsewhere`). Nothing is made in their place.

None of it reads English in code. The input is the engine's own lines and records; the
check is a closed question with the engine's codes, compared in code; the bodies follow
the guards' verdict and the attitude track.

## Tried and taken out

- **An `attacks` slot** (who goes at whom, landing or not), so a miss at the player out of
  a fight could be judged. On the bench (`tools/beat_verify_bench.py`, 2 runs) it took the
  blows the reader had reported as harm: harm claims 12/14 → 8/14 on the same beats (the
  harm alarm 2/6 → 1/6 after the second read, within what a rerun moves). A slot
  competing with its neighbour —
  CLAUDE.md's "a model asked for N things answers in parallel". `shown_here` alone caught
  every departed raider, so the slot went.
- **`shown_here` offered only the away codes.** The reader wanted to list the wagon
  master and the enum had no room for him: "Vyraxys is busy at the front" came back as
  the raider. Every code is offered now, and only the away are judged.
- **The `shown_here` instruction and demonstration on every beat.** The beats with
  nobody away lost harm claims they had read before: 12/14 → 9/14 on the same beats, in
  both of the two versions of the demonstration tried ("the commoner lunges forward,
  slamming their weight into you" no longer hurt the player). Now a beat with nobody away
  is asked word for word what it was asked before — checked: all 50 of the bench's
  earlier beats get the identical messages and schema, and their scores came back to
  master's (harm claims 12/14, harm alarm 2/6).
- **A demonstration of the away man swinging and missing.** A demonstrated miss teaches
  "a blow at you is no harm"; he leans on a rail instead.

## Measured

### The live replays (gemma-4-12B heretic, Ollama free of other clients)

Two saves at the moment the player fell (`a`: down at -3 after one blow; `c`: a second
fresh character), each replayed through both Continues; "before" is master a84bc9e,
"after" this branch, the same saves. A replay where the dice bled the player to death
in the downed door (a 410, no narrated beat) is not counted: 5 before (a third save,
`b`, died all three times and was dropped), 1 after.

| | before | after |
|---|---|---|
| narrated beats after the robbery | 8 (a ×6, c ×2) | 11 (a ×8, c ×3) |
| the departed raiders on the page, here and now | **8 of 8** | **0 of 11** |
| …swinging or lunging (at the player, the wagon, the drovers) | 7 of 8 | 0 of 11 |
| a thing the player does not carry ("your buckler") | 1 of 8 | 0 of 11 |
| bodies made by the beat | 0 of 8 | 0 of 11 |
| `beat-absent` repairs made | — | 0 (nothing to catch) |
| sentences the new check cut wrongly | — | 0 |

Read by hand, every beat. Before, the beat continued the fight: "The raider, his jaw
bruised and swelling from your blow, ignores the pain and lunges again" (a1), "The
raider's blade is a blur of motion, and you feel the steel bite deep into your side"
(a2 — the fight replayed whole), "the blade clanging against your buckler" (a4), "The
first raider recovers their footing, their face twisted in a snarl, and prepares for a
different, slower strike" (c2); the one that did not swing had the raider "backed away
into the haze of the dust" an hour after he left (a3). After, the raiders are where the
engine put them — "watching the horizon where the raiders vanished", "The two raiders
are gone, their tracks already fading into the scrub", "The bastards took the coin, but
they're still in the vicinity" — and the wagon master and the drovers talk about the
stolen gold. Measured: the input alone fixed it on these runs; the check had nothing to
catch.

An interim version of the check, before its second read asked who a sentence shows, cut
"Vyraxys is busy at the front, his voice now low and raspy" as the raider (the reader's
enum then held only the away codes, and the yes-or-no second read said yes). Probed on
six of the runs' sentences afterwards, the identity second read answered all six as it
should (the wagon master twice not the raider; the raiders four times, the one backing
away included).

### The bench (`tools/beat_verify_bench.py`, 2 runs, gemma-4-12B heretic)

55 beats: the 50 of 2026-10-03 and five from the replays above (`defeat-*`: three where
the departed raiders act, one where one backs away into the dust, one clean).

| | master (50 beats) | this branch (55 beats) |
|---|---|---|
| clean beats falsely alarmed, after the second read | 0 of 72 | 0 of 76 |
| `absent` alarms (the departed raiders) | — | P 1.00, R 5/6 |
| harm alarm, after the second read | 2/6 | 2/6 |
| harm claims | 12/14 | 14/16 (12/14 on the same beats; the two more are `defeat-replayed`'s) |
| every other category | | unchanged |

The one `absent` miss is `defeat-buckler` on the second run: the reader left
`shown_here` empty (it had listed both raiders on the first run). The live input fix is
the first line of defence; the check is the second.

## Not done, on purpose

- **An item the player does not hold** — the report's shield. Covered only where it sits
  in a sentence the check already takes off (before-a-4's "the blade clanging against
  your buckler" is the departed raider's lunge). A general "the player uses a thing they
  do not carry" read would need a closed vocabulary of things the player does NOT carry,
  which the engine does not have; not attempted.
- **Other doors that carry the scene on unnarrated.** Only the downed door marks its
  lines `moved_on`. "The fight is over." and the award lines after a fight are not
  marked — they follow a narrated beat and carry numbers — and are left as they were.
- **In a fight** nothing changes: the prose-call input change applies whenever a door has
  marked lines since the last beat, which the downed door does only once the fight is
  over.
- **New bystanders** were not reproduced in these replays (0 bodies made in any before
  run); the struck-sentence rule and the walk-in refusal are proved by the tests, with
  the reading stubbed, not live.
