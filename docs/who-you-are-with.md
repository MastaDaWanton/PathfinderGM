# Knowing where you are, and who is with you

*Written 2026-09-22, from a report made after four sessions in one settlement.*

> "I have never been aware that vormoor was a village. this should be one of the first
> things done when you are being dropped into a world. A description of the place you are
> in that lets you know what to expect. and if you have picked a background and are know to
> the place you start then the person you start next to does not need to be a stranger.
> they could be a friend or travel companion. and if you are taveling together they should
> follow and comment on the world around you."

Three things, and each of them was a fact the engine already held and had never handed to
anybody.

---

## 1. The scale never reached the player

`rules/places.population` — the one function in the app that says what a village *is*, in
words a player can act on — had **no production caller anywhere**. One test read it. It was
written when places shipped and nothing ever called it.

Meanwhile the scale reached the narrator's brief from the very first turn:

```
HERE: Vormoor, a village.
```

So the model knew what kind of place it was and the player did not, for four sessions. That
is the worst shape this class of defect takes: the asymmetry is invisible from both sides.

**What changed.** `places.what_it_is(scale)` is one composer with three readers:

| where | what it says |
|---|---|
| the opening | "Late morning in Vormoor, a village of a few hundred people, and everyone knows everyone." |
| the brief | `HERE: Vormoor, a village of a few hundred people, and everyone knows everyone.` |
| the panel | `Vormoor · village · urban · 10:42`, with the full sentence on hover |

Three sentences saying this three ways is the drift CLAUDE.md names, so there is one.

The panel matters more than the opening: an opening is read once, and this player had
played four sessions. A band in words and never a figure — the third law is that no model
authors a number, and "fifty thousand" in a brief is something a model starts doing
arithmetic with. A scale this app does not price (a "hamlet", a "quarter") says the word
the world used and claims no size, rather than inventing a population for somebody else's
world.

## 2. You are not a stranger where your background says you are known

Eleven of the fourteen shipped backgrounds are **local**, and they say so in their own
words:

- *"You kept a pitch at the market and the neighbours still nod."*
- *"You grew up at the lodging and the room still quietens when you come in."*
- `knows.every-face-here`

And the opening put a stranger beside every one of them. Half the app already knew —
`campaign._standing` stops calling you "a stranger here" the moment ties bind — but that
was the *prose*. The scene's state said nothing, so the narrator wrote a stranger.

**What changed.** `backgrounds.acquaint` runs once at campaign start, right after the ties
bind. If any tie bound a place in this settlement, the person the opening already rolled
becomes somebody who knows you: the attitude track moves to `friendly` (1e's own word for
somebody who "will chat, advise, offer limited help") and they carry `bond.knows-you`.

**Nobody new is added**, and that is deliberate. On 2026-09-20 the same player reported the
opposite defect — *"drenn ironvale is named as part of my background but does not belong in
the scene"* — and `bind`'s `place=False` answers it. That stands. What changes is who the
one person already there *is* to the player, not how many people there are.

A character with no local tie keeps their stranger. Being new somewhere is a legitimate way
to start, and `exile` is the background for it.

The opening says it, and the brief says it, and both read the tag rather than deriving it
again:

> "The queue has stopped moving. The old man ahead of you, who has known you long enough,
> has stopped to watch."

## 3. Companions follow

Both movement doors shed every non-PC not named in `with`, for a good reason their own
docstring gives — a gatekeeper wounded in the city once followed the party to a forest and
took an NPC turn for the rest of the session. But `with` asks the *model* to remember who
the party is on every single move, which is the one thing a language model reliably does
not do. Measured live the same day, on a turn where the player did nothing but cross a
village:

```
Left behind: Drenn Ironvale.
```

**What changed.** `bond.travels-with-you` is a state on the person, granted and lifted by a
new `company` op, and both movement doors read it. Inform's Van Helsing (*Recipe Book*
7.13, Traveling Characters) is the same rule from the other end: the follower is a property
of the character, and the movement rule reads it — not something the author re-states each
time somebody moves.

```json
{"op": "company", "params": {"who": "c2"}}
```

From then on they move when the party moves, through every travel and every journey,
without being named again. `{"do": "leave"}` ends it.

**Who may come** is decided by the attitude track in its own words rather than a new rule:
`friendly` "will chat, advise, offer limited help", `helpful` will "take risks to help".
Walking somewhere with you is the first of those. Anyone below it is refused with the fix
named — talk them round, which is a Diplomacy `check` the engine already resolves and
already limits to once a day per person.

**And a bug the work uncovered**: `_op_journey` never moved its escorts at all. `with` on a
journey was honoured in the shedding and forgotten in the arrival, so anybody named in it
was left standing at the far end of a road they had just walked — present in the store,
absent from the scene. Nobody had noticed because naming somebody in `with` on a journey is
a thing that had never once happened in play.

### Commenting

The brief now says what the engine holds:

> *Marra TRAVELS WITH the player: they came here together and they go on together. They
> have their own eyes and their own opinions about what is around them.*

That is deliberately a fact and not a script. The prior art is clear about which works:
Dragon Age: Origins and DA2 triggered banter **by location** — you passed a spot and it
fired — while Inquisition moved to a **timer** and players measured the result as too
sparse and too random. The trigger here is the same as DA:O's and it is free: the narrator
already writes a paragraph on arrival, and the arrival instruction already asks it to end
on one particular person doing one particular thing. A companion in the room with stated
opinions is a person it can reach for. No new turn loop, no banter table.

## And a stale rule, found while fixing this

The op briefing still carried yesterday's travel rule:

> "If reaching somewhere means passing through another place first, travel to that place
> this turn and go on the next."

That was true until the route-finder landed and false the moment it did. It is CLAUDE.md's
"when you fix a rule, grep for every copy of it", committed inside the very piece of work
that rule exists for. Corrected, along with `venture`'s `parent` (which must now be where
the party stands).

## Audited against the three laws

Done after the fact, against `.claude/skills/states-effects-tells`, and it found one real
fault in this work and one stale claim in the contract itself.

**One vocabulary.** `bond.knows-you` and `bond.travels-with-you` are constants in
`rules/states.py` beside `role.guard` and `state.wanted`, and every reader asks
`has_state(states.KNOWS_YOU)` — no site spells the tag. Not `TAGS` rows: those map
condition keys to tags, and neither of these is a condition, which is the same reason
`WANTED` and `BYSTANDER` are constants too.

**The fault.** `_op_company`'s first cut read `states.attitude_of(who)` and compared the
answer to `("friendly", "helpful")` — a reader matching attitude strings, which is
precisely what law one forbids. The three-laws ratchet did not catch it and could not:
it counts literal *condition* keys per file, and an attitude word is not one. Fixed to
ask the track — `attitude.step_of(mood) < attitude.step_of(attitude.COMES_ALONG)` — with
the threshold named once in `rules/attitude.py` where the rest of the track lives. Writes
still take a key (`settle_attitude(who, "friendly", …)`), which is how every caller of
the one applicator works; the law is about readers.

**One applicator.** The bond is an `ActiveEffect` through `Actor.apply_effect`, removable
by source, and the attitude moves through `Engine.settle_attitude` — added as the public
name for `_set_attitude` rather than letting `backgrounds` reach for a private method,
because a second copy of clear-then-add is exactly what that method's docstring exists to
prevent. Nothing in `rules/ontheway.py` applies an effect at all; the cutpurse's coin
leaves through `goods.spend`, the one door money leaves a purse by.

**Severed tells.** `company` emits one. `acquaint` does **not**, and that is worth saying
plainly: it applies an effect at campaign start, where there is no Outcome to carry a
tell. It is the same shape `backgrounds.bind` has always had, and the fact reaches the
narrator the way an attitude always has — as a stated fact in the brief rather than as a
tell. Consistent with what is already there, and still an asymmetry with `_op_condition`.

**And the contract's ledger was stale.** It listed "no route from a social check to an
attitude" as open after stage 8. It has been closed since 2026-09-16 — `_sway_subject`
takes the intent's own `target`, the book's DC and steps come from `rules/attitude.py`,
and `_set_attitude` applies it. That matters here because `company`'s refusal *names* that
route ("talk them round — that is a Diplomacy check"), and a refusal naming a fix that
does not exist is worse than no refusal. Proved end to end rather than assumed:
indifferent → the player's own Diplomacy roll → friendly → they come along. The skill's
ledger is corrected.

## What is still open

- Nothing makes a companion act on their own between turns. They speak because the
  narrator writes them, which is enough for remarking on a street and not enough for a
  companion who should refuse to go somewhere.
- `acquaint` marks the one person the opening rolled. A scene that already holds a crowd
  gets nobody marked — it declines to guess which of them is the friend.
- A companion carries no loyalty, and nothing takes the bond away except the player saying
  so. Being walked into a fight they did not want should cost something.
