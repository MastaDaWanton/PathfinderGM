# Continue, polish and the guards that over-reached

Group 4 of the fix pass after the 2026-09-18 play-test (`docs/playtest-2026-09-18.md`,
items 23, 22, 11, 10). Branch `continue-and-guards`. Tests:
`tests/test_continue_and_guards.py` (10).

## The ruling on Continue (item 23)

"Continue should work as I have nothing to add and continue the scene, not as nobody
does anything. My character should keep doing whatever he is doing and the scene should
move forward without any addition from me. If I am running a machine and a fight breaks
out, if I then hit continue my character should keep running the machine as more of the
fight plays out, and if I keep hitting continue the fight should play out further and
further, even coming to an end, having the authorities called."

The shipped design was the inverse: Continue's three worked examples demonstrated
"nobody fills the gap", "he waits", "nothing has been decided either", and the model
wrote exactly that seven beats running in the brothel. The directive's own text reached
the planner as the player's words: `say` of "in their own words, and let the people and
the place here go on…", `give` of "scene on" three times, `use_item potion_of_rest_01`.

### What was built

- **Continue is a directive, never an utterance.** `plan_turn` asks the model for no plan
  at all on a Continue: one `narrate_only` (`_continue_plan`) — a legal delay in a fight,
  after which the NPC loop runs with dice; out of a fight the world moves through the
  prose call. The directive never reaches an injector as the player's words.
- **The standing action is a fact.** `judgement.standing_action` renders the thread's
  doing and subject ("they go on working at the bellows") plus "THE WORLD MOVES ONE
  BEAT … Nobody merely waits", last in the prompt with the scene block. A fight keeps
  the standing action as `thread["standing"]`, silent to the anchor and the brief,
  alive for Continue. The thread verbs learned a fifth family — work, run, operate,
  tend, mind, pump, steer, hold — and match after "and", so "go to the forge and work
  the bellows" sets a thread.
- **The three Continue examples** show a standing action held while the world moves:
  the bellows kept going while two men fight in the dust and somebody shouts for the
  watch; a harness-maker answering and setting the strap down; the line at the gate
  moving and two guards coming the other way. None shows a stalled room; a test holds
  each to three action sentences.

## Polish keeps the events (item 22)

Every prose turn in the brothel was under the 800-character floor and went to `polish`,
whose drafts replaced her actions with atmosphere ("The woman continues her work…" →
"The timberer's rhythmic thud…"). Now: `narration.action_sentences` finds the sentences
in which somebody does something (a person as subject — pronoun, cast role word or
name — with a verb that is not merely being; questions excluded); a draft whose only
faults are `too-short` and `no-hand-back` ships at its own length when it carries three
or more; and a rewrite that keeps fewer than 60% of the draft's action sentences
(`actions_kept`: the same sentence, or two of its content words in one sentence) is
refused whatever its score. The floor is for prose that is wrong, not for prose that is
shorter than asked.

## The guards (items 22, 11)

- **The escape claim** is a claim only when somebody here is held (`state.held` — a
  grapple, a pin, an entanglement) and only when asserted: "She doesn't pull away" is
  negated, in a room where nobody held anybody, and was cut as "states an escape".
- **The phrase guards** exempt the only other person's handle when the room holds two:
  "the woman" / "the girl" opening every beat of a two-person room is not a formula, and
  "the woman with the basin" recurring is her being there.
- **The world's lowercase vocabulary** joins the known names: a capitalised token is
  invented only if its lowercase form appears nowhere in the world's text. "the Reeve's
  men" was struck because the export says "reeve" in lowercase and the model
  title-cased it — the same class as the Council/Elders false positives, 27 of 31 flags.
  Kaida, Vorgath and Keldor appear in no world text and stay caught.
- **The renamer minds its article** (done in group 3): "the Reeve's men" → "the men",
  "at the Reeve" → "at the stranger", never "the the".

## The opening (item 10)

Not a cold load: the model wrote "Maste" for "Masta", the invented-name check counted it
as a name from outside the material and the who-the-player-is check found no "Masta" —
two rejections from one slip, and an 802-character draft fell to the template.
`opening_prose.repair_near_misses` substitutes a name one letter off (or sharing its
first four letters within a letter of length) with the real one before the checks run,
sentence starts included; `opening._clause` lowers a leading article in a spliced fact
("keeps to a local reeve", not "keeps to A local reeve"), and only an article — the
export's own case is otherwise kept.

## Measured live, one replay on a copy of the `masta` save

Seven lines: go to the forge and work the bellows; Continue; Continue; the insult;
Continue; Continue; Continue.

| | Result |
|---|---|
| Continue asks the model for a plan | never — six of six logged "continue: no plan asked of the model" |
| The world moved | a guard turns and steps toward the shout; a merchant's cart wedges into the lane and is shoved free; the smith pauses mid-swing, then stops his advance; the crowd thins |
| The directive as the player's words | gone — no `say` of the directive, no `give` of "scene on" |
| Polish | "kept at its own length: too-short only, and the draft carries its events" on three beats |
| The fight | none: the insult became an Intimidate check the model chose, and nobody struck. A fight that does not open cannot be run to its end; the opener from group 1 waits on a described blow |
| The standing action | **not set**: "go to the forge … and work the bellows" matched no thread verb → the fifth verb family, and the match after "and" |
| Names in narration | the pool names leaked ("Kael Throk", "Soren") → the true name left the brief (group 3's record) |

## Left open

- On Continue in a fight the delay is the player's whole turn; a setting for total
  defence instead is a small door not yet cut.
- The fight the ruling describes running to its end and bringing the authorities depends
  on the fight existing; the replays that had one (group 1) ended in a kill within two
  presses. A longer replay with two combatants is the measurement still owed.
