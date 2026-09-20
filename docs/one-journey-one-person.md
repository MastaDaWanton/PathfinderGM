# One journey a turn, and one card a person

Group 14 of the fix pass after the 2026-09-19 play-test
(`docs/playtest-2026-09-18.md`, items 35 and 36). Branch `one-journey-one-person`.
Tests: `tests/test_one_journey_a_turn.py` (6), `tests/test_one_person_one_card.py` (11).

Both items were found by the live checks of groups 7 and 8 rather than reported by the
player, and both were recorded with a plan and deliberately left for their own group.

---

## Item 35 — four travel ops in one plan walk the party across town

### What it measured

"I find the mayor and grab him by the collar" came back as a plan of **five `travel`
ops**, and the engine ran them in order:

| op | result |
|---|---|
| `travel {"place": "the guildhall"}` | resolved |
| `travel {"place": "the market"}` | resolved |
| `travel {"place": "the lane"}` | resolved |
| `travel {"place": "the green"}` | resolved |
| `travel {"place": "the upper floor of the guildhall"}` | refused — *the stairs to it are inside the guildhall* |

The party ended standing on **the green**, a place it had merely passed through, while
the prose described the market. Nothing capped movement per turn: `travel` validates one
place at a time and each one was legal on its own.

### How often, actually

The item asked for this, because "if a plan of four travels is common, the prompt is
inviting it". Measured 2026-09-20 across every save in the scratchpad, **deduplicated by
campaign and turn** so that copies of one save could not count the same turn eight times:

> Of **222** unique planned turns, **2** carried a `travel` at all — and **neither
> carried exactly one**. One had two, one had five.

So it is rare, and it has never once happened correctly. The first count, before
deduplication, said 8 of 342; that was the same two turns counted across save copies, and
the corrected number is the one above.

### The prior art, and the thing it settles

Every tradition asked the same question and gave the same answer: **the traveller names a
destination, and the system finds the way.**

- **Inform 7.** The Recipe Book's own extensions: *Misadventure* lets the player `GO TO` a
  named room and calculates the best route; *Safari Guide* makes the whole trip in a
  single move, opening doors on the way. One named room in, route derived
  ([Inform Recipe Book 6.9, Going](https://ganelson.github.io/inform-website/book/RB_6_9.html)).
- **Angband and DCSS.** Travel picks a destination and computes the path; the walk is
  spread over turns and is *interruptible*, and after an interruption "repeating the
  previous command will recompute the path and start along that path"
  ([Angband manual, Command Descriptions](https://angband.readthedocs.io/en/latest/command.html)).
- **Pathfinder 1e** has nothing to say here, and the item was right that it does not:
  out of combat a "turn" is not a defined unit in the rulebook, so this is a turn-structure
  question, not a movement one.

In none of them does the traveller hand over the route. Here the model was doing exactly
that, and the engine was executing each hop as a full arrival — shedding the cast, laying
the ground, staffing the place — for rooms the party only walked through.

### Built

`Engine._journeyed`, the same shape as `_battle_joined` and reset in the same place and
for the same reason: a fresh batch is a fresh question, and `resume` does not reset it
because a resume continues the same declared turn. The first `travel` that actually moves
the party sets it; every later `travel` or `journey` in that batch is refused with where
the party now stands, so the next turn can carry on — the roguelike's "repeat the command
to resume".

**The first is kept, not the last**, and the measured turn is the argument. The
destination the model meant — the upper floor — was reachable only from a place earlier in
its own list. Collapsing to the last would have refused a legal journey; keeping the first
preserves the invariant that the party only ever arrives somewhere it could legally reach
from where it stood. A travel that moves nobody — a refused destination, or the ground
already underfoot — does not spend the turn's journey, or a plan that opens by restating
where the party is would strand it.

The prompt says it too, in both places that describe travel (`CLAUDE.md`: when you fix a
rule, grep for every copy of it) — "ONE travel a turn. Name where the party ENDS UP, never
the route they walk to get there." The refusal is the mechanism; the instruction only
stops the prompt inviting what the engine then has to refuse.

### Proved live

Driven on a copy of the save that produced it, with a player input that names a route:

    > I walk to the well, then on to the market, and then up to the guildhall
      PLAN: ['travel', 'travel', 'travel', 'travel']
      OUT: You are at the well now. Left behind: …
      OUT: The party has already travelled this turn and is at the well. One journey a
           turn — the rest of the way is the next turn's.          (x3)
      PARTY AT: the well

    > Take me from here to the mill and then to the gate
      PLAN: ['travel', 'travel', 'travel']   -> one made, two refused, party at the market

    > I go to the market, grab bread from a stall, then head to the green
      PLAN: ['narrate_only', 'travel']       -> one travel, untouched

One more thing that run turned up, recorded and **not** fixed here: on a turn whose single
`travel` was refused ("the stairs to it are inside the guildhall"), the prose still
described climbing them. Prose contradicting a refused op is its own defect and belongs
with the narration guards, not with this one.

---

## Item 36 — one person booked twice under two descriptions

### What it measured

The ledger came back holding **merchant** and **shouting merchant**, both at turn 82, out
of one beat:

> "A man in a heavy, grease-stained leather apron stands behind the counter … and he is
> currently shouting at **a merchant** over a dispute regarding a shipment of timber. …
> The crowd is dense, and his attention is currently divided by **the shouting merchant**."

The head-word dedup lets a second person through when the description differs, *on
purpose*: "the man in the leather apron" after "desperate man" is a second man, and
skipping him is exactly how the man who swung first at the player was never put on the
board (2026-09-18, item 16b). So it could not tell these two apart from the words alone.

### The prior art

The article can tell them apart, and the account is old and settled. Heim's
novelty/familiarity condition: an indefinite noun phrase **creates a new file card**, a
definite **refers to one that already exists**
([File Change Semantics and the Familiarity Theory of Definiteness, 1983](https://www.jimpryor.net/teaching/courses/hyper/heim1983.pdf)).
The metaphor is not an analogy here — `scene.cast` *is* a ledger of cards for the people
the narration has introduced, which is the thing Heim's files model.

The same source supplies the limit. Definites are routinely **accommodated** when they are
novel — the first mention of somebody can perfectly well be "the reeve" — so a definite
naming a role nobody has booked still books, unchanged.

### Built, and then widened by driving it

`_refers_back` reads the article and asks whether the ledger can show *who* a definite
refers to. Three grounds, each measured rather than supposed:

- the role word was booked by **this beat** — the reported turn;
- the ledger holds that role **bare** — "merchant" booked, then "the merchant with the
  satchel": a bare card is somebody nobody has described yet, and a definite describing
  them is the description arriving, not a second body;
- the description **shares a word** with a booked one of the same role.

It began as the first ground alone, which is all the reported turn needed. Three turns
driven live in the market on 2026-09-20 showed that was the narrowest case rather than the
whole shape — **one man collected three cards across three beats**:

    turn 94: man with a distinctive      <- the description truncated at the adjective
    turn 96: man with the distinctive
    turn 98: man with the satchel

and a porter collected two ("a porter with a scarred forearm", then "the porter with the
scarred forearm"). So the rule reaches across beats, and the comparison drops the role
word from both sides — leaving it in would make every pair sharing a role the same person,
which is the dedup this replaces.

That run also exposed what made those three phrases fail to match each other. The
adjective slot before the noun was a closed list plus `-ed`/`-en`: "scarred forearm"
survived because *scarred* ends in `-ed`, and "distinctive satchel" was cut to **man with
a distinctive** because *distinctive* matched nothing. Fixed with morphology rather than
more vocabulary — `-ive`, `-ous`, `-ful`, `-less`, `-ish`, `-ing` join `-ed` and `-en` —
and the slot stays narrow deliberately: widening it to any word lets a verb in, because
"a man with a sword lunges" would read *sword* as the adjective and *lunges* as the noun.

### The line it must not cross

Stated in its own test, because this rule is one careless generalisation away from
re-breaking the fix that put the man who swung first onto the board: "desperate man"
booked, then "the man in the leather apron" — same role, nothing bare, no shared
description — is still **two men**.
