# In conversation

Ruled at the table 2026-09-24, and built the same day.

> *"a discussion/conversation should be only while directly speaking to a person or
> being spoken to you must end the conversation or walk away purposefully ... make sure
> exiting conversation is easy to do with a button, I should be able to deny/ignore
> talking with someone ... a chat window ... the names of the people involved (people
> should be able to join or leave the conversation) and their attitude toward me
> quantified ... I want to be able to talk with then and increase that attitude until
> they Idolize/Love me."*

## The prior art, and what it warned against

Everweave's Update 15 ("Friends & Strangers") shipped a structured Dialogue Mode: a
conversation screen with the NPC's portrait, NPCs that "can call for skill checks when
what you say is worth testing", and separate tracking of what the player intends and
what the NPC hears. Its own later notes record what went wrong: "you may need to state
more clearly when you want to leave a conversation", scenes ending "prematurely",
"intrusive skill checks during basic NPC conversations", state-tracking bugs, and a
Creative Mode shipped to bypass the whole system after the backlash. The rules and the
dice there all run inside the language model, so none of that state is engine-owned.

Three things follow, and each is a rule here:

1. **The state is engine-held.** `states.TALKING` is a tag on the person, granted and
   lifted through the one applicator. The scene has no dialogue flag; who is in the
   conversation is `Engine.talking_to()`, the same question as every other state.
2. **The exit is explicit and free.** One op (`leave_talk`), one button, no model call,
   no roll. Silence never ends a conversation.
3. **Nobody in a conversation asks the player to roll.** A check comes only from what
   the player does; the brief says so in as many words.

## How it opens, how it ends

Opens when the player addresses somebody (`say` with a `to`, or a `say` in a room with
exactly one other person), or when somebody addresses them — an NPC's quoted line in the
beat that speaks to "you", attributed by the same head-word matching the introductions
use (`judgement.hailed_by`).

Ends only when the player takes their leave or refuses to answer (`leave_talk`, the
panel's button), walks out of the place (`travel`, `journey`, `venture` say "You leave X
mid-sentence"), or the other party leaves it — walks out, goes down, or draws
(`_settle_talk` at the end of every batch, said).

## What it shuts, and what it does not

| | combat | conversation |
|---|---|---|
| Craft action | gone | greyed, with the engine's sentence |
| Rest | refused | refused: "mid-sentence, take your leave first" |
| Trade | gone | open — buying is a conversation |
| Cast | open | open, and seen by the room |

## Regard: attitude, quantified

The book's track (`hostile … helpful`) is a state a check sets for 1d4 hours and has no
memory. **Regard** is the memory: a 0–100 score kept on the person as one effect
(`attitude.set_regard`, tag `states.REGARD`, `amount` the score), the track's baseline
when nothing is holding a step, and the number the panel shows. A sixth step,
**devoted**, sits above helpful; Diplomacy still stops at helpful as the book says, and
only regard climbs there.

| what | regard |
|---|---|
| an exchange in conversation | +2, at most three a day per person |
| Diplomacy success | +8 per step moved |
| Diplomacy failure by 5 or more | −5 |
| Intimidate success | −5 (cowed, and they remember) |
| a gift, no price on it | +3 |
| a permanent shift (a background's "knows you", a warrant) | baseline set to that step's floor |

Bands: hostile 0, unfriendly 15, indifferent 35, friendly 55, helpful 75, devoted 90.

The third law holds: the narrator is told a step crossed, in the vocabulary's word, and
never the number. The number is the player's, on the panel.

## Files

`rules/attitude.py` (regard), `rules/states.py` (`TALKING`, `REGARD`, `devoted`),
`rules/engine.py` (`talking_to`, `join_talk`, `end_talk`, `_settle_talk`,
`_op_leave_talk`, the say/sway/give hooks, the rest and craft refusals),
`gm/judgement.py` (`hailed_by`), `gm/prompts.py` (the IN CONVERSATION block and the op),
`play/views.py` (`talk_act`, the `talk` and `busy` payload), `play/templates/play/table.html`
(the panel). Tests: `tests/test_in_conversation.py`, `tests/test_regard.py`.
