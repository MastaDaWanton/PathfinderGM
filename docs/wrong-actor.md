# A creature's turn, told as somebody else's

*Design record, 2026-09-27. The code is `gm/narration.py` (`wrong_actor`, `right_actor`,
`creature_nouns_for_pc`, `pc_to_second_person`), `gm/agent.py` (`_repair_wrong_actor`,
`_groom`, `narrate_outcome`, `npc_turn`), `gm/prompts.py` (`call_two_messages`,
`CONSEQUENCE_NPC_EXAMPLE`, `actor_repair_messages`) and `play/views.py`
(`_run_npc_turns`, `_plain_tells`). The tests are `tests/test_wrong_actor.py`. The
measurement is `tools/narrator_audit.py --script fight --turns 12`.*

## The report

`python tools/narrator_audit.py --script fight --turns 12` on gemma-4-12B, 2026-09-27:
with the new player-intent interpreter on, **8 of 12** turns flagged `third-person-pc`;
with it off (the control), **2 of 12**. Every flagged sentence sat in the narration of an
ENEMY's turn, after the beat's "What do you do?":

- "Kesst Vayr with the marked knuckles lets out a low, guttural growl, his grip
  tightening on the tankard" — the enemy is Borin; Kesst Vayr is the player;
- "Kesst Vayr's frantic movements fail to break its hold, leaving it pinned firmly
  beneath your grasp" — the player is grappling the enemy.

## Is it the interpreter? No

- **By the code.** The reading (`GMAgent.reading`, `gm/interpret.py`) is read by
  `plan_turn` and nothing else. `npc_turn` builds its own prompt from the scene brief;
  the consequence call (`narrate_outcome` → `call_two_messages`) is handed the plan's
  wind-up, the tells and the reasons; `_groom` never looks at it.
- **By measurement.** Rerun on the same code the same day: reading **on 2 of 12**,
  reading **off 3 of 12**. The 8 of 12 was a run that grappled — every enemy turn after a
  grapple gave the model more chances to fall into the shapes below — not the reading.

## What the enemy-turn beats actually held

Read back from the recordings (`--record`) by replaying every creature-turn reply through
`_groom` against the scene it was written for. NPC-turn repairs were not logged anywhere
before this, which is why the replay was needed; they are now (`npc-turn` rows carry
`repairs`).

**Every one of the five flagged turns in the two reruns was put on the page by our own
grooming, not by the model:**

| run | the model wrote | the page read | by |
|---|---|---|---|
| on, t5 | "…and **the beast's** momentum carries it past you" | "…and **Kesst Vayr's** momentum carries it past you" | `creature_nouns_for_pc` |
| off, t3 | "**The creature** lunges with a desperate, frantic energy" | "**Kesst Vayr** lunges…" | `creature_nouns_for_pc` |
| off, t4 | "**The beast's** momentum carries it forward, but its strike misses your guard" | "**Kesst Vayr's** momentum…" | `creature_nouns_for_pc` |
| off, t7 | "**The creature's** claws collide with Kesst's chest" | "**Kesst Vayr's** claws collide with **Kesst's** chest" | both |
| on, t9 | "…against **Kesst’s** temple" | unchanged | the name swap's guard |

- **`creature_nouns_for_pc`** was written 2026-09-18 on the premise that when everyone
  else present is a person, "a creature noun can only mean the player", and swapped it
  for the player's *name*. The biggest man in the room is a brute and a beast to the
  narrator, and on his own turn the noun is him. The swap also ran *after*
  `pc_to_second_person`, so the name it wrote stayed a name and `third-person-pc` fired on
  our own repair.
- **`pc_to_second_person`** returned early unless the text contained the *whole* name.
  A beat saying only "Kesst" was never looked at.

**Underneath, the model does turn creatures' turns round — and the name swap hid it.**
Across the committed corpus (38 creature-turn consequences) and the first live run, **8
of 100** creature-turn beats gave the creature's act to "you":

- "You weave through the panicked crowd … close the distance to the heavy door" — for
  "Borin Lyraxys moves from near to near.";
- "With a sudden, violent surge of effort, you wrench your body sideways … to break the
  hold" — the grappled man's own turn (the grapple case the report suspected; the tell
  was a plain, unambiguous "moves", so it is not the tell being read backwards);
- "You lunge forward, swinging your blade toward Kesst Vayr" — which the name swap turned
  into "…toward you", a sentence the audit then scored clean.

The cause is the prompt's shape. The consequence call opened **"The player said: Borin
Lyraxys acts"**, and its one worked example has a tell naming the player ("Ashka Verel
makes the Reflex save by 3") answered as "you". The demonstration taught, exactly, *the
tell's subject is "you"* — and on a creature's turn the subject is the creature.

## Prior art

- **Inform 7's adaptive text** (Writing with Inform §14.1–14.3,
  <https://ganelson.github.io/inform-website/book/WI_14_3.html>): one report of an action,
  "[The actor] [put] [the noun] on [the second noun]", printed "You put the revolver on
  the table" when the player acts and "General Lee puts the revolver on the table" when
  anyone else does. The story's viewpoint is applied by the *system* at report time, not
  guessed by whoever writes the sentence. That is the model for rendering the tells in
  the player's person before the narrator sees them.
- **Ian Bicking, "Roleplaying driven by an LLM"** (2024,
  <https://ianbicking.org/blog/2024/04/roleplaying-by-llm>): the LLM confusing the player
  with another character is "a common issue and can happen quite often even with a custom
  prompt". Consistent with this project's first law — a prompt fix alone will not hold.
- I found no published measurement of role inversion in second-person LLM narration;
  the 8-of-100 figure above is ours.

## What was built

1. **The source.** On a creature's turn `call_two_messages(acting=…)` says "It is
   Borin Lyraxys's turn, not the player's. Borin Lyraxys acted; the player's character is
   "you"", shows the tells with the player already as "you" (Inform's move — the model
   has no name to put on anybody), and demonstrates a creature's turn
   (`CONSEQUENCE_NPC_EXAMPLE`: the ferryman swings, "you duck") instead of the player's.
   The player's own turn is unchanged.
2. **The check** — `narration.wrong_actor(text, acting, pc_name)`, and the `wrong-actor`
   finding (weight 3, with `wrong-hands`). On a creature's turn it flags:
   - the player's name and "you" in one sentence — always two people, only one of them
     the player;
   - the player's name wearing somebody else's descriptor ("Kesst Vayr with the marked
     knuckles");
   - a beat that never names the creature (a name word, its head noun, or a creature noun
     opening a clause) and says "you" — the whole beat turned round. On the corpus every
     inverted beat left the actor out and every sound one named it, bar one ("He shifts
     his weight…"), which costs a repair and no more.
   It runs in `_groom` **before** the name swap, which is what hid the inversions.
3. **The targeted repair** — `GMAgent._repair_wrong_actor`: one model call per beat, only
   when the check fired, shown the tells and the one sentence at fault; kept only if the
   rewrite passes the check. The standing polish stays off on creature turns — a sound
   beat still costs one call (pinned).
4. **The backstop** — `narration.right_actor`: a beat turned round whole is replaced by
   its tells, rendered for the page (numbers off, the player as "you"); otherwise only the
   flagged sentences go. Agency is a fact of the tell, and the tell is always true.
5. **Our own backstops fixed.** `creature_nouns_for_pc` no longer swaps in a sentence that
   already says "you", nor — on a creature's turn — a noun opening a clause; what it does
   swap goes through `pc_to_second_person`. The name swap looks for the first name, and
   takes the curly apostrophe. The two creature-turn raw-tell fallbacks in
   `_run_npc_turns` now put the player in second person (the player-turn fallback already
   did).

## Not done, on purpose

- ~~**The maneuver tells**~~ — done, 2026-09-27; see "The maneuver tells" below.
- **The player's own consequence call** still shows tells naming the player in the third
  person. The same Inform move would likely help there too; it is unmeasured, so it is
  left alone.
- **The audit's `third-person-pc`** is now nearly unreachable on a creature's turn by
  construction; the audit reports the `wrong-actor` repairs and backstops beside it
  ("what grooming did to the creatures' turns"), which is the number to watch.

## Paired runs after the change

`tools/narrator_audit.py --script fight --turns 12`, gemma-4-12B, 2026-09-27, all four on
the same afternoon; "raw" is the model's own reply before any grooming, measured by
running `wrong_actor` over the `--record` file.

| run | page: `third-person-pc` | clean | creature-turn consequences | raw: wrong way round | raw: player named | total time |
|---|---|---|---|---|---|---|
| before, reading on | 2 of 12 | 9 | 8 | 3 | 4 | 464 s |
| before, reading off | 3 of 12 | 8 | 6 | 1 | 3 | 386 s |
| after, reading on | **0 of 12** | 12 | 9 | **0** | **0** | 430 s |
| after, reading off | **0 of 12** | 12 | 9 | **0** | **0** | 407 s |

- **The source fix did the work.** Raw inversions went from 4 of 14 creature-turn
  consequences to 0 of 18, and raw mentions of the player's name from 7 of 14 to 0 of 18:
  the model is no longer shown a name to misplace, and is shown a creature's turn to copy.
  Two runs a side is a small sample; the corpus test pins the check, not the model's rate.
- **The repair fired twice live (after, reading off), and both times earned its keep —
  though neither was the model turning a beat round.** In each, an earlier deterministic
  cut had removed the one sentence that named the actor before the check ran: the
  outcome-claim repair cut "The thug lunges forward, his fist connecting squarely with
  your ribs", and `cut_dead_men_walking` cut "The thug lets out a desperate, rattling
  groan…" because a *second* actor named "thug" was dead (a name collision, flagged as its
  own task). The remainder said "you" with no thug in it; the rewrite gave "The thug
  strikes you with a heavy blow…" and "The thug, despite its broken state, crawls toward
  you…". About one second each.
- **The backstop never fired live.** It is exercised by the tests only.

## The maneuver tells (2026-09-27, the follow-up)

*Code: `rules/tables.py` (`MANEUVERS`, `maneuver_text`, `third_person`), the success,
degree, extra-distance and backfire lines of `Engine._resolve_maneuver`, the sheet's
maneuver rows in `rules/sheet.py`, and the manoeuvre verbs in `narration._YOU_VERBS`.
Tests: `tests/test_maneuver_tells.py`.*

### The defect

The table wrote every consequence in the attacker's second person and the engine spliced
it into the tell raw. On a creature's turn the consequence call shows the tells with the
player already made "you", so the thug's drag reached the model as **"Borin Lyraxys
drags you by 0: you drag the target 5 feet."** — seen live on the old code (below). Two
more faults rode along: the lead was `name + "s"` ("bull rushs"; "You trips the thug"
once the player's tells went through `pc_to_second_person`), and a creature's backfire
told the player they fell or dropped their weapon.

**`wrong_actor` cannot see it.** "The thug drags you by 3: you drag the target 5 feet."
names the actor and carries no player's name, so it scores clean — and the backstop that
replaces a bad beat with its tells would have printed it. The fix had to be at the source.

### What was built

Inform's adaptive text again, now at the table (Writing with Inform §14.3: "[The actor]
[put] [the noun]" printed "You put…" or "General Lee puts…"; Diku's `act()` fills `$n`
/ `$N` per message the same way). Each sentence is a template: `{actor}` and `{target}`
for the two people, `{actor's}` / `{target's}` for their possessives, `[verb]` in its
"you" form, agreeing with the nearest person before it. The engine renders every tell
in the third person by name — "Borin Lyraxys drags Kesst Vayr by 3: Kesst Vayr is
dragged 5 feet." — and the player becomes "you" downstream in the one place that
already does it, `pc_to_second_person`. The character sheet renders the same templates
with the player as "you" and the other as "the target". Each manoeuvre has its own lead
verb; drag's effect is passive, so lead and effect do not say the same sentence twice.
A test holds `_YOU_VERBS` to every `[verb]` in the table.

### Live, paired, same afternoon

`fight` script, 10 turns, the user's default models (gemma-4-12B heretic). A scratch
harness drove the real HTTP loop and swapped only the creature's *chosen intent* for a
manoeuvre at the player (drag, trip, grapple, bull rush, disarm, overrun in turn), so the
engine, the tell, `call_two_messages(acting=…)`, the model, `_groom` and the page are the
real path. Every beat read by hand.

| run | creature manoeuvre beats | successes | backfires | tells shown with the attacker as "you" | raw prose the wrong way round | on the page |
|---|---|---|---|---|---|---|
| before (8e27ed2) | 8 | 2 (drag ×2) | 1 (disarm, by 11) | 3 | 1 | 1 |
| after | 16 | 8 | 0 | 0 | 0 | 0 |

- **Before, the backfire put the defect on the page.** The creature's disarm failed by
  11; the tell read "…fails against Kesst Vayr by 11. You drop the weapon you were
  using."; the model wrote "your weapon is ripped from your hands"; `wrong-hands` cut
  that, and the tells standing in for it told the player **"You drop the weapon you were
  using."** It was Borin's to drop. `wrong_actor` flagged nothing.
- **The two old drags came out the right way round** despite "you drag the target" in
  the prompt — the model read the lead. The defect is a contradiction in the prompt the
  model sometimes resolves, not one it always obeys.
- **After, all 8 successes read the right way round** — "Borin's hand clamps onto your
  shoulder … He yanks you backward" for "Borin Lyraxys drags you by 10: you are dragged 5
  feet. You are dragged another 10 feet." `wrong_actor` fired on 3 of 16 raw beats, all
  three read by hand as the right way round (the creature called "the warrior", "the
  Korvu", or the player resisting a failed drag): the known cost of the never-named rule,
  one repair each.
- **Backfire after**, in a third short run (5 turns) with the creature's CMB d20 forced
  to a natural 1 plus a -10 harness handicap, since a natural 1 alone left the thug at
  -9: the same disarm told "Borin Lyraxys's disarm fails against Kesst Vayr by 24. Borin
  Lyraxys drops the weapon used for the disarm.", and the page read "The weapon slips
  from its grasp … leaving it momentarily unarmed." One beat — the trip backfire was not
  reached live, and is pinned by the tests.

### Still open

- Several manoeuvres tell outcomes the engine never applies — the disarmed item is not
  dropped, the stolen object does not move, nobody is pushed, dragged or repositioned,
  and dirty trick's tell lists six conditions while applying only `dazzled`. Flagged as
  its own task; the tell and the state have to agree before the narrator can.
- A success by exactly 0 still reads "by 0".
