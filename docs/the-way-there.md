# The way there

*Written 2026-09-22, from a request made with the market's tray open.*

> "it should be that i can say i go to the market and the narrator doesn't just put me in
> the market but describes all the places i needed to move through to get there then
> describes positionally where i am in the market what's around me and where I can go from
> where i am. then It should describe the action taking place around me the buying and
> selling the sounds and smells and finally hone in on some specific action or actions that
> the PC sees or hears to draw the users attention.
>
> not that i have to spend four turns to get to the market. however if it is 4 places i move
> through there should be some kind of NPC encounter table that rolls for chance encounters,
> perhaps my journey is stopped short because as im moving through the streets a child
> pickpockets me or I get blocked by a pedestrian squabble. these should not happen every
> time but occasionally.
>
> the chance should roll for every movement and it should roll on the table for the
> respective area im moving through and stop rolling if an encounter hits.
>
> the same should apply to over land travel."

Three things, and they are separable: **the route is walked**, **every hop is checked**, and
**an arrival is written as an arrival**.

---

## 1. The route is walked

`Place.exits` was written the day places were, and until now nothing in the app ever read
it for movement. A `travel` was one assignment of `Scene.at` however far across town it
went. The engine's own refusal for a five-travel plan said why it could not do better:

> "the destination the model meant was reachable only from a place earlier in its own
> list, and the engine has no route-finder to walk it there"

`places.route(places, start, dest)` is that route-finder: breadth-first over `exits`,
returning the hops after `start` and ending at `dest`, `()` when there is no path. The
tradition is unanimous about whose job this is — Inform ships `the best route from X to Y`
and its Recipe Book examples (Misadventure, Safari Guide) take one named room and derive
the path; Angband and DCSS compute the path and walk it, interruptibly. In every one of
them the traveller names the destination and the system finds the way. Here the *model* was
being asked to hand over the way, which is the one thing it cannot know.

**It costs one turn, not four.** That was explicit in the request and it settles the
question item 47 left open: one journey a turn (item 35) is unchanged, and a journey is now
a whole crossing rather than a step.

Measured over both shipped worlds, on 76 settlements:

| hops between two places | pairs |
|---|---|
| 1 | 3,144 |
| 2 | 2,954 |
| 3 | 2,824 |
| 4 | 5,338 |
| no route at all | 40 |

Mean **2.726**. The 40 unreachable pairs and eight one-way exit links are why an empty
route is not a refusal: the caller falls back to the single step this door has always
taken, so nothing that worked yesterday stops working.

## 2. Every hop is checked

`rules/ontheway.py`. The app had exactly one wandering check in it — `gathering`'s, once
per foraging expedition, because Ultimate Wilderness says to — and crossing an entire city
rolled nothing at all.

**The road's number is published and is used verbatim.** Archives of Nethys, *Step 4:
Create Random Encounter Tables*: check four times a day, 20% each. A watch is six hours and
each watch is a 20% check. A part-watch gets a pro-rata share, because the most common move
in the game is the single hour `_op_travel` charges for stepping outside the walls, and
rounding that up to a full watch would make leaving town as dangerous as a dawn-to-noon
march.

**The street's number is derived from it.** Rolling 20% per *hop* would interrupt 60% of
crossings, which is the thing the source itself warns about ("too many random encounters
can slow down the progression of your plot and can frustrate players"). So the per-hop
chance is set so a crossing of the measured average length comes to the published 20%:

    1 - 0.8 ** (1 / 2.726) = 0.0786  →  8%

One step across the square is 8%; a four-hop city crossing is 28%. The longer way across
town is genuinely riskier, which is the whole reason the check is per movement.

**The street table** is authored to the temper of the AD&D 1e DMG's city encounters — the
oldest published version of this table and still the only one that is mostly *not* a fight.

| d100 | what |
|---|---|
| 01–22 | the way is blocked — a cart, a drover |
| 23–42 | two of them going at each other, and a crowd watching |
| 43–58 | a hawker who has decided you are buying |
| 59–72 | a beggar |
| 73–86 | the watch, looking at faces |
| 87–96 | a hand in your purse |
| 97–100 | somebody who means it |

Four bands in a hundred are violence. At a 20% crossing that is about one street fight in
every 125 crossings, which is the "occasionally" the request asked for and is not a number
anybody would have arrived at by feel.

**The cutpurse is rolled, not decided.** Sleight of Hand DC 20 to lift a small object from
another person, opposed by the mark's Perception (Core Rulebook). Both rolls are the
engine's and both are hidden — being *asked* to roll Perception is itself the tell that
something is being taken, which is the oldest way there is to ruin this encounter. The coin
leaves through `goods.spend`, the one door money leaves a purse by.

**Nobody is invented.** The street's people are grounded through `npcs.choose` against the
loaded corpus, the same door `rules/roster.py` uses; the road's come out of the bestiary by
the ground's own biome and a CR window around the party. They arrive through `_bring_in`,
the one door creatures come in by, and they stand where the party stopped.

**It stops rolling at the first hit**, as asked, and the walk stops there: the destination
shrinks to the hop that was interrupted, and the tell says where the party had been making
for. That is Angband's and DCSS's disturb rule, and the reason a refusal here is not a dead
end — the player repeats the command and carries on.

## 3. Overland, the same

A journey is checked watch by watch before the march is charged, so the body only pays for
the hours actually walked. A hit stops the party on the open ground the route crosses —
not back in town, not at the far end — and `Scene.road` remembers how much road is left, so
the next turn's journey walks only the remainder. Charging the whole road twice would make
being interrupted a punishment for the dice rather than an event.

A multi-day road will usually take several turns now, with something happening on each.
That is what overland travel is at a table.

Not at sea: a passage is not a march, and a ship's own trouble is `rules/ships.py`.

## 4. And the narrator is told

An engine that walks a route and rolls a table changes nothing the player reads unless the
narrator is told — every defect in `docs/playtest-2026-09-18.md` that survived a correct
engine survived it that way.

- The tell names the places the way ran through, in order. The narrator cannot describe a
  route it has to infer; a model left to infer one invents streets.
- The brief says what is **next door** (the exits, by name) as distinct from what exists,
  and says plainly: name the destination, never the route.
- The brief says what is **underfoot** — the same `floorplan.Shape` the tactical map is
  drawn from, so the stalls the prose describes are the stalls the player can climb on.
- The prose call, on an arrival turn only, asks for an arrival: the way in, then where you
  are standing and what is in reach, then the work and noise and smell of the place, ending
  on one particular thing one particular person is doing, close enough to speak to.

That last one is deliberately **not** a numbered five-sentence skeleton. This repo's own
rule is that the shape of a prompt becomes the shape of the output, and a template would
produce five identical arrivals. It names what the passage owes the player and leaves the
sentences alone. It fires off the engine's own tell rather than a flag, so it cannot
disagree with what happened.

## What is still open

- The patrol band knows nothing about the warrant. A wanted character who meets the watch
  in the street is told the watch is looking at faces and nothing follows from it. The gate
  is still the only place the law is enforced (`docs/wanted.md`).
- The road's table has two bands. A washed-out ford, a toll, weather that costs a day —
  all of those want mechanics that do not exist yet, and an authored line with no teeth
  behind it is worse than no line.
- Nothing rolls for a `venture` into ground gone into, which has its own hours.
