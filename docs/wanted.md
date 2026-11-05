# Wanted

The law's opinion of a character, per town, and the three places in the app where it
bites. Plan section 6.6 of `docs/quest-schemes-plan.md` named the state; this is what
was built for it (2026-09-08), what was measured, and what is still open.

## The vocabulary

Two tag families in `rules/states.py`:

    state.wanted.<town>      a name and a warrant
    state.suspected.<town>   a name on the watch's lips

`<town>` is `states.town_tag(location_id)`: the settlement's durable World Bible id,
lowered, with anything that is not a letter, digit or hyphen folded to a hyphen. Never
the town's name — two towns can share one, a town can be renamed, and either would land
a warrant on the wrong ground. Per town, not global: Skyrim keeps its bounty per hold
for the same reason (a Falkreath crime is nothing to a Winterhold guard), and it is the
shape a scheme wants — "A Small Favour" makes you wanted where the favour went wrong.

They are **not** rows in `TAGS` or the condition table. A condition key is one fixed
state with one fixed set of tags; these are a family with the town in the leaf, so
there is no row to write. They exist only as an `ActiveEffect` through the one
applicator:

    ActiveEffect(kind="situation", duration="until-dismissed",
                 source="scheme:<id>/<outcome>" | "rule:<id>",
                 tags=(states.wanted_tag(location_id),))

`states.wanted_tag` / `states.suspected_tag` are the only writers of the tag text, and
`states.standing_with_the_law(actor, location_id)` — `"wanted"`, `"suspected"` or
`""` — is the one reader, the way `attitude_of` is for the attitude track. No gate,
counter or guard spells the tag itself. `has_state` is a prefix match at a dot
boundary, so `state.wanted.abc` does not answer for `state.wanted.abcd`; and
`has_state("state.wanted")` still answers the family question "wanted anywhere?".

Deliberately under `state.*` (readers refuse on it) and deliberately outside
`state.down`, `state.unable`, `state.impaired` and every `recovery.*` family: a warrant
stops no action and a night's sleep must not clear it. `test_a_warrant_is_not_slept_off`
rests the character and checks the warrant is still standing.

A third tag, `role.guard`, says who keeps the law here. The watchman template counts by
kind; a document or the GM may grant the tag to a named person through the applicator.

## Reader one: the gate (`Engine._op_travel`)

A wanted character is refused two ways out of the town whose ground they stand on:

- a travel to the place named "the gate" (matched on the name, so "the merchant's
  gate" — the GM's dressing — still resolves to it through `places.find`), and
- the open road: a travel by **biome** off urban ground, which never touches the gate
  place and would otherwise let a wanted character leave by not naming it.

The town is read off the place id (`places.location_of(scene.at)`), falling back to
`scene.location_id` only when the id cannot say, so a warrant from the last town does
not shut this one's gate. The refusal is a printable outcome through `Engine._refuse`,
never a raise, with the fix named: the founded and ventured places outside the walls if
any exist (listed by name), else "ground you have founded or ventured into", and in
either case "or clear your name".

Those other ways are real: `venture` is its own op and is not watched, and a travel by
name to a place already made outside the walls (yesterday's cave) is not the gate and
not the road. Moving inside the walls — the tavern, the temple — is not watched either;
wanted is not house arrest.

Suspected is a line in the tell — "the guards at the gate look twice, and let you
through" — and never a refusal. That is the whole difference between the two states at
the one door where it is felt.

## Reader two: prices and the counter

`rules/pricing.py`:

    WANTED_MARKUP = 1.5
    SUSPECTED_MARKUP = 1.25

**This app's rule, not the book's.** The Core Rulebook prices goods and never asks who
is buying. Ultimate Campaign's Reputation and Fame runs Fame from -100 to 100 and spends
prestige on favours without touching a price. The video-game traditions split: Skyrim
keeps a bounty per hold and never moves a merchant's prices; Fallout: New Vegas has
merchants refuse the Vilified outright and charges nothing extra in between. Neither
gives "suspected" any teeth, and this app needs a lesser state that bites without
shutting a door. So: half again for the wanted — the price of a stallholder's silence,
felt on every jar without making bread unaffordable — and a quarter for the suspected.

`pricing.markup_for(buyer, town)` is the reader; `pricing.worth(item, buyer=, town=)`
and `pricing.what_a_shop_pays(item, seller=, town=)` apply it. Both columns move: a fence
who charges a fugitive more pays them less for the same reason. Called without a buyer
the answer is the open price, which is what the shelf is drawn against
(`market.on_sale`) and what a catalogue prints.

The counter (`play/views.py`, `_counter_refusal`, asked by both `trade` and `trade_do`)
refuses the wanted outright with the merchant's name and the reason: "wanted here, and
nobody keeping a counter will be seen trading with them. Clear your name, or trade
somewhere the watch is not looking." The suspected are served at the markup, and the
panel's JSON carries `law` so the page can say why the numbers moved.

## Reader three: the guards (`Engine._law_joins`)

When a first swing opens a fight (`_ensure_encounter`) on the ground of a town where a
player is wanted, every bystander who is the law — `has_state("role.guard")`, or the
watchman template by kind — joins the side against them through `join_fight`, the same
door `rally` uses, so they arrive with an initiative roll, a side and a square. The
attack's own tell names the sides, so the guards appear in "squares off against"
without a second sentence. A guard already sided (an escort the GM put on the player's
side) is left where they were put. No warrant, or a warrant in another town: the
watchman stays the civilian `rally` already says he is.

## Removal

`Actor.remove_effects(source="scheme:<id>/<outcome>")` — one call — and every bite is
gone: `test_clearing_the_name_is_one_removal_and_every_bite_evaporates` holds the gate
refused and the price marked up with the effect, removes the one record, and checks the
gate opens at the open price with nothing else touched.

## Measured

- Seventeen tests in `tests/test_wanted.py`, each docstring naming what it prevents;
  the whole suite green with them (run 2026-09-08).
- The pangrella fixture's Vyrakon has no "back streets" — its settlement set is the
  market, the gate, the tavern, the temple, the guildhall and the mine head — which the
  inside-the-walls test learned by being refused.

## Open

The first three entries below were open when this was written and are closed now;
each keeps what it said, with what closed it (checked against the code 2026-10-01).

- ~~**The narrated road pays the open price.**~~ `Engine._op_buy` and `_op_sell` called
  `pricing.worth(found)` and `pricing.what_a_shop_pays(held)` without a buyer, so a
  purchase made by *saying* it — the sell/buy injectors — was not marked up.
  **Closed:** both now pass the keyword the fix named,
  `pricing.worth(found, buyer=actor, town=place)` and
  `pricing.what_a_shop_pays(held, seller=actor, town=place)`, so the narrated road and
  the counter panel price alike.
- ~~**A GM-declared fight.**~~ `_op_begin_encounter` named its own sides and was not
  second-guessed; guards joined only through the first-swing door. **Closed:** it calls
  `_law_joins()` now, the same as that door.
- ~~**No granter yet.**~~ Nothing in `content/schemes/` granted either tag. **Closed,
  three ways.** A scheme: "A Small Favour" grants `state.wanted.$town` when it opens and
  `state.suspected.$town` on its bad outcomes, with `$town` an implicit slot every scheme
  has, filled from `states.town_tag` of the settlement it opened in
  (`schemes.IMPLICIT_SLOTS`) — the document never spells the town. A rule: a break-in
  somebody sees (`Engine._witnessed_break_in`) makes the character suspected the first
  time and wanted the second, the warning before the warrant. And a provocation: insult
  somebody orderly enough in town and they go to find the watch, which lands suspected
  on a character the law had no opinion of yet (`rules/provocation.py`). All three
  apply through the one applicator, with the rule or the scheme named as the origin.
- **The town beyond gate, price and guards.** No innkeeper turns the wanted away, no
  card opens on the visible side ("the guards say ..."), the brief does not tell the
  narrator the character is wanted; time does not soften wanted to suspected. Each is a
  reader to add, none needs a new store. (A guard who SEES the wanted now comes for them:
  "Reader four" below. The watch still does not go looking where it cannot see.)
- **Bounty hunters outside the town** (Skyrim above 1,000 gold) — refused for now: the
  state is per town on purpose, and a hunter on the road is a scheme, not a reader.


## The way past the watch (added 2026-09-08)

A wanted character who holds `knows.way-past-gate` — a witness's smuggler's door, a
scheme's reward, anything granted through the applicator — may take the open road
(a travel by biome off urban ground). The gate itself stays shut to them: the way
past the watch is not the arch. `tests/test_a_small_favour.py` drives it.


## Reader four: the arrest (added 2026-11-01)

The owner's ruling that day: guards who see a wanted person move to arrest them. Measured
on the report that asked for it (Corvin, turns 56-61): wanted in Reedsink, the player stood
beside the captain and two guards for six turns and nothing happened. `rules/arrest.py`
holds the design and the research (Skyrim, Oblivion, Kingdom Come, Baldur's Gate 3; 1e has
no arrest procedure, only Diplomacy and Bluff). In short:

- At the end of a batch out of a fight, a `role.guard` here who can see the player
  (`awareness.sees`) begins the arrest: `law.arresting` on the player, one effect, with the
  tell naming the four answers.
- The player's next batch answers it: a blow opens a fight the law joins
  (`_law_joins`); being somewhere else is running — away, warrant standing, the next guard
  tries again; a Diplomacy or Bluff check made stands the watch down for the day
  (`law.stood-down.<town>`), missed, they take you; anything else is going quietly.
- ~~**Taken is provisional and the owner's call**~~: held through the night and released at
  morning for want of proof. **Replaced** the same day by the trial, below.

Tests: `tests/test_arrest.py`. ~~The scheme's captain carries no `role.guard` tag~~ —
**closed**: the owner's ruling 2026-11-01 ("officers arrest too"). A Small Favour grants its
captain `role.guard.officer`, which answers `has_state("role.guard")` by the prefix, and a
save opened before that heals on the next scheme tick (`schemes._heal_cast_grants`).


## The trial (added 2026-11-01)

The owner's ruling: "you are held questioned and if found guilty charged appropriately, with
murder being a death sentence. you should always have to ability to talk your way out of
things. but if you cant then either you pay your fine and have stolen goods confiscated or
worst case are executed. or you can escape from your cell or during the walk to your
execution." `rules/trial.py` holds the design and the research; every number is a row of
`content/rules/law.json`, cited or marked HOUSE.

**Writer two: a crime somebody saw** (`trial.report`, after the deeds reader in
`Engine._drive`). A deed row the law charges (`law.json` `deeds`) with a witness in town:
a guard who saw it, or a killing anybody saw, is a warrant at once; anything else is
suspected the first time and wanted the next (the break-in's ladder). The warrant carries
what it is for in its payload (`crime`), as the break-in's and A Small Favour's (`charge` in
the scheme grant) now do.

**Custody** (`law.custody`, one effect, the stage in its payload):

| stage | the player's next batch | the batch's end |
|---|---|---|
| questioning | Diplomacy (attitude DC + Make Request's row for the proof), Bluff (vs Sense Motive at the proof's believability) or Intimidate (10 + HD + Wis) | made: charges dropped (Intimidate: let go, warrant standing); missed or silent: guilty, or let go for want of proof |
| plea | the same three, mercy: simple aid +5 for a second request | sentence: death → commuted to the blood price if made; a fine → waived if made |
| condemned | Disable Device (simple lock 20, +10 no tools), Escape Artist (bars 30), Strength (good wooden door 18), a bribe (Ultimate Intrigue: 25% of Table 14-9) | escaped: free, wanted; else dawn and the walk |
| walk | escape (Escape Artist or CMB vs the escort's best CMD) then a run (a walk while still held is refused: measured live, "I go to the gallows" planned as a travel to the gate was rolled as a dash and freed the man), or a fight | broke away: free, wanted; else hanged (`Actor.die`) and the death screen |

A fine is paid from the purse; what it cannot pay is worked off at a labourer's wage (1 sp a
day), at most thirty days. The stolen goods go back to their owners, every warrant of the
town is lifted and the judged deeds are never charged again. Beaten by the law where
wanted is being taken in (`play/downed.py` → `trial.beaten`); beaten on the walk, the end.

Tests: `tests/test_trial.py`, one per half of the ruling.

**The owner's answers (2026-11-01, second round).**

- *Killings.* "be sure that letting someone bleedout or killing someone who attacked you
  durring combat are not murder and instead manslaughter or assault". So:

  | what happened | charge |
  |---|---|
  | a beaten foe killed after the fight (`deed.kill.captive`) | murder |
  | somebody who raised no hand, struck dead by the player's own act (`deed.kill.unprovoked`, manner `blow`) | murder |
  | the same victim dead after the player's harm — bled out, or another hand (manner `after`) | manslaughter |
  | an attacker killed in the fight (no deed row: the watch's own eyes, `trial.watch`) | manslaughter |
  | an attacker the player dropped dying who bled out within a day | manslaughter |
  | careless or accidental kill | manslaughter |
  | striking somebody who raised no hand, no death | assault |
  | fighting off an attacker, no death | uncharged |

  The blow that killed merges into the killing (one charge, its assault judged with it),
  and a death that comes after the blow keeps the witnesses who saw the blow. A
  guard-witnessed self-defence kill is a warrant for manslaughter: 10 gp, talk at the
  "caught" row (+15), the plea waives it.
- *No proof, released.* An accusation with no witnessed deed and no stolen goods behind it
  — A Small Favour's frame-up — falls at questioning: "The accusation of murder falls for
  want of proof", its warrant lifted; with nothing else charged the player walks out and
  every warrant of the town goes. Consequence: that scheme's clue steps need the warrant,
  so its "Clear your name" card can no longer tick once the frame-up has fallen.
- Fines, the 30-day labour cap and the bribe stand as built. Careless harm short of a death
  stays uncharged (unanswered). Help from outside the cell is not built.
