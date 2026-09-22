# Closing the list

*2026-09-22. The five items left open after the 2026-09-19 play-test, and what each turned
out to be.*

---

## 39 — the class tables were documents nothing read

`rules/precision.py` was the **only** thing in the app that read a class table's `grants`.
Bravery, armour training, weapon training, trap sense, uncanny dodge, trapfinding, rogue
talents, master strike, arcane bond and arcane school were printed on the Class tab and
read by nothing.

And one of them had been made **wrong** by shipping sneak attack. Sneak attack keys off the
defender being flat-footed; uncanny dodge is the rule that stops a 4th-level rogue ever
being caught flat-footed. The trigger went in without its counter, so a rogue took dice
they are immune to — a coherence problem group 15 introduced, not an old gap.

**A reader, not a special case.** The contract's own worked judgment is that a class
ability "does not need a special case in the engine; it needs a field in the `grants`
grammar, applied generically", and `test_three_laws` pins that the engine names no class
ability. So `rules/classfeatures.py` turns every row of every table into a tag:

```
grants: ["uncanny dodge"]           ->  class.uncanny-dodge
grants: ["sneak attack 3d6"]        ->  class.sneak-attack
grants: ["trap sense +2"]           ->  class.trap-sense
```

The number stays in the table and is read by whoever needs it, exactly as
`precision.dice_for` already reads the sneak dice — so a homebrew class that grants uncanny
dodge at 6th is right for free. Joined to `Actor.standing_tags`, live-read like a feat's
tags and a race's: nothing is stored, and correcting a class table corrects every character
of it.

| feature | reader |
|---|---|
| uncanny dodge | `Engine._flat_footed` |
| improved uncanny dodge | `position.flanking_with` |
| evasion / improved evasion | `_op_save`'s damage branch |
| sneak attack | `rules/precision.py` (group 15) |

Each rule is the book's, with its exceptions kept: uncanny dodge still loses Dex **if
immobilized** (asked as `is_helpless`, this app's owner for that clause, never as a list of
condition names); improved uncanny dodge yields to an attacker **four levels above** the
class that granted it; evasion needs **light armour or none** and **not helpless**.

Improved uncanny dodge is read in `flanking_with` rather than in `precision`, deliberately:
the book says "can no longer be flanked", so the +2 to hit goes with the sneak dice. One
answer, two readers.

**And the flat-footed rule was written twice** — once in the attack path, once in the
manoeuvre path. Found by going looking rather than by anything failing. One reader now.

**What is still inert, and why.** Stated in the module and pinned by tests that fail the
day a trigger arrives, so the note cannot go stale:

- **bravery, trap sense** — both are bonuses on a save against a *descriptor* (fear,
  traps), and `save` carries none: its params are `save` and `dc`. Adding one would put
  the trigger in the model's hands, which the third law forbids. It waits for a descriptor
  that comes from a document.
- **trapfinding** — no trap-finding check exists to bonus.
- **armour training** — `max_dex` and `acp` are read off the armour row at the point of
  use; there is no per-character adjustment channel yet.
- **weapon training** — needs weapon **groups**, which the weapon table does not carry.
- **rogue talent, arcane bond, arcane school** — choices, not grants: they need a level-up
  picker, which does not exist.

## 42 — one number for two allowances

A sorcerer had `2` and a bard `4`, as a single cap covering spell levels 0 and 1 together.
So the forge offered 279 spells across both levels against two picks, and a player could
spend both on cantrips and **begin play unable to cast anything at all**.

The book gives both classes four cantrips *and* two 1st-level spells. Both full twenty-level
Spells Known tables were **fetched from the SRD rather than recalled** — CLAUDE.md's warning
is that a table like this is "90% right from memory", and the 90% is the part nobody
notices. They live beside the slot tables in `rules/casting.py`, which already types out
1e's irregular progressions for the same reason.

`creation.allowance(class, level, int_mod)` is the one answer:

| class | allowance at 1st |
|---|---|
| sorcerer, bard | `{0: 4, 1: 2}` |
| wizard | `{1: 3 + Int}` — cantrips are a **grant**, not a budget |
| cleric, druid, paladin, ranger | `{}` — they prepare from the whole list |

The forge shows one budget line per level and greys a level whose allowance is full. The
build refuses a level **left unopened** as well as one overspent — which is the actual
defect, since a sorcerer with two cantrips and no spell passed every check before. And the
wizard's granted cantrips are declared in `CASTERS` as `grants_levels: [0]` rather than as a
literal in the forge, so a homebrew class can say the same thing.

## 45 and 38 — one rule, not two

**45**, with the map open: *"i am at a gate with wagons passing through and a wagon off to
the side this map is completely wrong."* The map was right. The engine held the party at
**the well** and drew it faithfully. Vormoor has no gate.

**38**, found live: a `travel` refused with *"the stairs to it are inside the guildhall"*,
and the beat then described climbing those stairs and reaching the landing.

Both are one defect: **a beat set where the party is not.** The narrator was told, twice
over — "The party is at the well. Not anywhere else in Vormoor", then "THE PLACES HERE (the
only ones that exist)" — and nothing checked whether the prose obeyed.

`narration.stands_elsewhere` checks the prose against **engine state**: `Scene.at` and the
places that exist. The vocabulary — read from `rules/places.py`, never typed twice — is used
only to recognise that a phrase *is* a place claim. A real place that is not the one they
are in is item 38; a vocabulary place this settlement does not have is item 45.

It is a weight-3 finding alongside `contradicts-the-engine`, because a beat in the wrong
place is not badly written, it is untrue, and every later turn inherits it. The repair names
the real place and the real list.

**Precision over recall, and the limit is worth stating.** It does not fire on seeing a
place, on somebody else going there, on crossing one on the way, on speech, or on scenery
the generator could never name ("a work yard"). Catching that last one would mean deciding
an unknown noun phrase is a room rather than furniture — the word-list trap the player has
objected to twice, and they are right about what happens next.

## 37 — "I have no crown to display"

The player typed *"I pull out my crown and display it for all to see"* and the narrator
produced one, the yard falling silent around it.

Measured against a sheet carrying one club, `false_claim` caught "I am the lost heir of the
old kings" and caught **nothing** for "I pull out my crown", "I show them my royal seal",
"I hand him the deed to the mill" or "I draw my longsword". So it was never about crowns:
any gear the player named was conjured, a weapon they had never bought included.
`_sheet_vocabulary` had been reading `pc.carried()` the whole time and nothing ever asked it
this question.

It is the possession half of a law this app already keeps for people — group 8 built
`rules/scope.py` so nobody is created on the strength of a phrase. The tradition is the one
that settled group 8: Inform's parser looks through what is in scope and refuses what is
not, *"You can't see any such thing."* A noun does not enter play because somebody said it.

**Shape, then sheet**, exactly as `false_claim` works, and for the reason the player gave
the first time: they would find a way around a word list. The shape is
producing/showing/handing/wearing with a definite article; the sheet then decides, out of
what is carried, worn, equipped, in the goods ledger, in the satchel, in the purse, and the
props this character is holding.

**It uses the door that exists.** The item's own note: "The answer is already built and
already ratified by the player — it just has the wrong door." So a false possession returns
from `false_claim` itself and travels everything a false claim already travels: the Bluff
the room rolls against, the prose told to hold it false, the finding that catches prose
making it true, and the crowd's reaction. The 2026-09-18 ruling was the player's own — *"It
should read as my character being delusional and the people should see it similarly"* — and
a man flourishing a crown he does not have is that act with a prop in it.

Sixteen lines were measured against a real sheet to set the shape. Three narrowings came
out of it, each because the first cut fired on something innocuous:

- **verbs**: production and display only. `offer`, `give`, `place` turned "I offer him a
  drink" into a delusion beat.
- **articles**: `my`/`the` only. "a drink" names a kind of thing, not a particular one.
- **taken from somewhere** is acquiring, which the engine has doors for: "I take the bread
  from the stall" is a buy, not a man producing bread from his coat.

### Two regressions the suite caught, both worth recording

**A shadowed name.** The first cut called its exclusion set `_NOT_A_THING` — and this file
already had one, which `_is_a_thing` reads. Defining it twice meant "I accept the offer"
started minting an item again and a chair leg stopped being one. Seven tests failed. Renamed
to `_NOT_A_POSSESSION`, and the abstract-noun set is now **reused** rather than copied: an
abstract noun is not a possession either.

**A guard that guessed.** A thin test double with no gear to read turned "I draw my sword
and hold it low" into a delusion beat. A sheet that cannot answer the question now judges
nothing — the same discipline as `fire_context` and `here` in the reviewer.

## The smaller threads, closed the same day

Each of these was recorded rather than built while the big items were in flight, and each
had a reason. The reasons are what changed.

**The street patrol now reads the warrant.** It shipped as a band that told a wanted
character the watch was looking at faces and let nothing follow. The gate is still where a
warrant is *enforced* — `docs/wanted.md`, reader one — and this is the second reader: what
it adds is that the street stops being safe once your name is on the list. A clean name
gets the ordinary patrol; a suspected one is looked at twice; a wanted one brings them
straight at you, and they arrive hostile, which `_law_joins` already understands to mean
every guard in that town is on the other side. No arrest, because there is no arrest in
this app and inventing one here would be a rule with a single home.

**The road's table has four bands.** It shipped with two and a note: *"a washed-out ford, a
toll, weather that costs a day — all of those want mechanics that do not exist yet, and an
authored line with no teeth behind it is worse than no line."* Both new bands use
currencies the engine already had:

| band | what it costs |
|---|---|
| weather | hours, charged to the clock and the body like any other hours on the road — and **not** added to the road's remembered progress, because sitting out a storm gets you no nearer |
| toll | coin, *asked for* and never taken: the decision is the point, and an engine that deducted it would have made it a tax |

Weather is the one meeting that brings nobody: the road itself is what stopped you, and a
template drawn for it would have put a stranger in the rain with no reason to be there.

**A venture rolls for the hours it charges.** Going into ground was the one journey in the
game where the road was always empty — it charged the hours and checked nothing for them.
It checks now, against the ground being *entered* rather than the town above it: what lives
in the sewers is what the sewers hold.

**A companion's bond reads the feeling it was granted for.** Nothing but the player's word
ended it, so a friend walked on cheerfully after being given every reason not to. Somebody
comes with you *because* they are friendly — 1e's own word for "will chat, advise, offer
limited help" — so somebody who has stopped being friendly has stopped coming. One
question, asked of the same track `company` asks, and the effect is removed by source so
the bond and its contribution evaporate together. A mended temper is not a standing
arrangement: they have to be asked again.

**An arrival says the walk is behind them.** Measured live: the engine had the party AT the
north crossing and the beat ended "You are moving toward the crossing". A passage that
leaves them on their way contradicts the panel, the map and the next turn.

### And two things the suite caught on the way

The three-laws ratchet refused the first cut of the watch's recognition, which spelled
`add_condition("hostile", …)` — a literal attitude key in the engine. It goes through
`settle_attitude` now, with the bottom of the track named in `rules/attitude.py` beside the
step a companion needs, so no reader anywhere spells an attitude.

And `test_two_actors_in_two_places_survive_the_save` began failing intermittently: it
asserted that only the player stands in the new room, and a travel now rolls the street's
table against an unseeded campaign, so somebody the walk ran into may legitimately be
there. The assertion is the containment it was written for — the merchant is not here —
rather than the whole roster. An unseeded fixture that asserts a roster is a gate that lies
occasionally, which is the trap `test_foraging_fills_the_satchel` already records.

## What is still open after this

Everything `rules/classfeatures.py` lists as inert, and each is blocked on a thing that
does not exist rather than on effort:

- **bravery, trap sense** — need a save DESCRIPTOR. `save` carries `save` and `dc` and
  nothing else, and a descriptor supplied by the model would put a rule's trigger in the
  narrator's hands, which the third law forbids. It waits for one that comes from a
  document: a spell's descriptors, a hazard's row.
- **trapfinding** — needs a trap-finding check to bonus.
- **armour training** — needs a per-character adjustment channel for `max_dex` and `acp`,
  which are read straight off the armour row at the point of use.
- **weapon training** — needs weapon GROUPS, which the weapon table does not carry.
- **rogue talent, arcane bond, arcane school** — are choices, not grants, and need a
  level-up picker.

And one that is nobody's fault: `backgrounds.acquaint` marks the single person the opening
rolled, and declines to guess if a crowd is already standing there. That is the right
answer for an opening and the wrong one for a saved game being healed, which no path
currently takes.
