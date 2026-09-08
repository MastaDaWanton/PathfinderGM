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

- **The narrated road pays the open price.** `Engine._op_buy` and `_op_sell` call
  `pricing.worth(found)` and `pricing.what_a_shop_pays(held)` without a buyer, so a
  purchase made by *saying* it — the sell/buy injectors — is not marked up. The fix is
  one keyword each: `pricing.worth(found, buyer=actor, town=place)` and
  `pricing.what_a_shop_pays(held, seller=actor, town=place)`; those two ops were outside
  this change's file ownership. Until then the counter panel is the reader that bites
  and the narrated road is the leak.
- **A GM-declared fight.** `_op_begin_encounter` names its own sides and is not
  second-guessed; guards join only through the first-swing door. Calling `_law_joins()`
  after `_lay_battlefield` there is the same one line.
- **No granter yet.** Nothing in `content/schemes/` grants either tag; "A Small Favour"
  (plan §3, §6.9) is the first author. `_grant` in `rules/schemes.py` already writes
  `kind="situation"` effects from a `tags` list, so a scheme outcome carrying
  `{"tags": ["state.wanted.<town>"]}` works today — but the town leaf must come from
  `states.town_tag` of the scheme's settlement slot, not be spelled in the document.
- **The town beyond gate, price and guards.** No innkeeper turns the wanted away, no
  card opens on the visible side ("the guards say ..."), the brief does not tell the
  narrator the character is wanted, and the watch does not come looking; time does not
  soften wanted to suspected. Each is a reader to add, none needs a new store.
- **Bounty hunters outside the town** (Skyrim above 1,000 gold) — refused for now: the
  state is per town on purpose, and a hunter on the road is a scheme, not a reader.
