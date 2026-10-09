# Things have an owner, a source and a destination

Lane A of `docs/playtest-2026-10-03.md`, items 1 to 8. One sentence for the whole lane:
picking up, handing over, buying, selling and dropping did not go through one place that
knew where a thing came from and where it went. So items were minted from figures of
speech, sold goods stayed in the pack, coin was an item called "coins", containers held
nothing, and a drop copied the thing to a bystander.

The final inventory of the owner's `items` save read

    goods: {"brunt of the weight": 1, "crate": 1, "pouch": 1, "coins": 1}   purse: {}

after a session in which Kesst carried a crate, sold it to a clerk and pocketed the
payment.

## What the traditions do (researched before designing)

Searched 2026-10-03, primary sources where they could be had. A second pass re-fetched
every quoted sentence and struck three claims a summarising tool had invented (a list of
"problems with physical money" on Inform's money page, a "design rationale" for Circle's
numeric gold, a TADS preference for a single money object). None of those is used here.

**Inform 7.** A thing has one holder: *Writing with Inform* §13.4 lists containment,
support, incorporation, carrying and wearing as "five mutually exclusive ways" a thing is
joined to another, and §8.7 says a moved thing's contents move with it. The Standard Rules'
taking action is "the only way an action in the Standard Rules can cause something to be
carried"; removing-from converts to taking. Its check rules refuse taking other people and
"people's possessions" — and that rule does not read a stored owner: it walks up the holder
chain, and if a person holds the thing, it is theirs. Dropping puts the thing in the
actor's holder (the floor). Giving is implemented and then blocked by default (the "block
giving rule": the recipient has to agree). On money, the Recipe Book (§9.4) recommends a
number: money "behaves more like a liquid than a set of items", with coin objects only when
the physical coin matters (a vending machine).
(https://ganelson.github.io/inform/standard_rules/actns.html,
https://ganelson.github.io/inform-website/book/WI_13_4.html, RB_9_4.html)

**TADS 3 adv3.** Every Thing has one private `location`, changed only through
`moveInto`, which notifies both ends. Taking from an actor's inventory is refused by
default (`Actor.checkTakeFromInventory`). There is no library money class.
(https://www.tads.org/t3doc/doc/libref/object/Thing.html)

**Diku / Circle / tbaMUD.** Gold is a number on the character. Money on the ground is an
`ITEM_MONEY` object holding its amount; picking it up deletes the object and adds the
amount ("There were %d coins"), and dropping gold makes one. Shops buy at the item's value
times a `profit_buy` of at most 1.0, refuse what they do not trade in and say why ("won't
buy that", "can't afford it"), and tbaMUD clamps a shop's buying price below its selling
price "to prevent infinite money-making". Merging dropped coin piles was proposed and closed
`wontfix` (tbaMUD issue #86).
(https://www.circlemud.org/cdp/building/building-5.html, building-7.html; tbaMUD act.item.c)

**Pathfinder 1e.** Core Rulebook p.140, Selling Treasure: an item sells for "half its
listed price"; trade goods are the exception and change hands at full value, "almost as if
it were cash itself". Appraise (p.90) is DC 20 for a common item. Ultimate Campaign's
bargaining rules are meant only "for rare or unique items". **No rule was found for selling
something that has no listed price**, so the value used below is this app's, and says so.
(https://aonprd.com/Rules.aspx?ID=109, https://aonprd.com/Skills.aspx?ItemName=Appraise)

**Abandoned.** NetHack 3.4.3 shipped gold-as-an-object (`GOLDOBJ`) as "an experimental
feature", made it unconditional in 3.6.0, and its fixes file then lists a run of gold bugs:
a hangup save that duplicated gold, piles that would not stack, a 0-gold object from
dropping 2^32 gold. No stated reason for the change could be found. Inform ships giving
*blocked*, not absent. Inform demoted removing-from to a synonym for taking.

### Adopted

- **One holder per thing, one funnel that moves it.** `Engine._op_give` is the funnel (it
  already said one op covers picking up, handing over, buying and dropping), and every
  holder it can take from is asked in one function, `rules/holding.py`.
- **Ownership read off where the thing is,** with the props ledger's `owner` kept beside
  it (the Creation Kit shape this app already chose, docs in `Scene.props`). A thing taken
  out of a person's hands without their handing it over keeps them as its owner and is
  marked `stolen` (Creation Kit's flag).
- **Coin is a number, and a coin object exists only while it lies somewhere.** The purse
  is the number. Coin dropped on the floor or carried in a pouch is a props record with
  `contents`; taking it or emptying the pouch turns it back into the number (Circle's
  money object).
- **Shops buy at half** (PF1e and Circle agree), and a price the player names can only
  lower the offer, never raise it (`accept`, the existing cap; tbaMUD's clamp).

### Refused, with reasons

- **Gold as an inventory object.** NetHack's bug list after 3.6 is the measurement, and
  this save is the same failure in miniature: "coins" ×1 in the goods beside an empty purse.
- **Refusing every take from a person** (Inform, TADS). Here the narrator stages the hand-
  over ("he slides the pouch across"), and refusing would leave the narrated pouch
  unrecorded, which is the original 54-turn `narrate_only` failure. The take goes through
  and the owner stays on the record instead.
- **Bargaining rolls on every sale.** Ultimate Campaign itself limits them to rare items.
- **A money object that merges piles.** tbaMUD's `wontfix`.

### Could not confirm

- A PF1e rule for the value of goods with no listed price (Appraise and Bargaining are the
  nearest). The app's fallback is stated below as the app's.
- Whether Circle 3.1 (not only tbaMUD) clamps the shop's buying price.
- The exact adv3 default refusal text for giving.

## What changed

**One asking module, one moving op.** `rules/holding.py` answers the questions every
handover asks first: is this the same thing ("the Brunt of the weight" is "brunt of the
weight"), what is its head noun ("a pouch of coins" is a pouch, "the brunt of the weight"
is a brunt, "a chunk of wood" is wood), is it money, is it a container, what does a
person's own label put in their hands ("the merchant with a heavy pack"). `Engine._op_give`
is still the one op that moves things, and now asks, in order, before it lets anything
come "from the world, which never runs out":

1. a container named in `from_` ("the coins from the pouch"), or one in the taker's own
   hands that holds the thing;
2. the ground here (the props ledger's existing door);
3. a person here holding it on record (their goods), then a person whose label says so.

A thing taken from a person who did not hand it over moves to the taker and keeps that
person as `owner`, with `stolen` set, on the props ledger; the tell says so ("takes the
heavy pack from the merchant with a heavy pack, who did not hand it over; it is still
theirs"), and the brief already prints a carried thing's owner beside it. A price is
consent: a thing paid for is handed over, not stolen. Nothing reacts to the theft yet —
the record is the hook a reaction would read, and building one is not part of this lane.

**The actor of a give to somebody else is the giver.** `give actor=pc target=c13` used to
read as the smith taking one out of the air. A giver's thing is found by name the way
people say it (`holding.key_in`), in the goods and then on the shelf (`stock`, exact id,
base or name — never `consumables.resolve_stock`'s content-word guess, which would hand
over the wrong jar). Somebody else's pockets stay open the way the world is (the clerk who
slides a pouch across was holding one); the player's never are, and coin never is.

**Selling goods.** `_op_sell` sells a thing out of the pack when it is not a jar
(`Engine._sell_goods`): the thing goes into the buyer's goods, the coin into the purse,
at half of `pricing.goods_worth` — the Core table price where a table lists the thing
(a hooded lantern, 7 gp, sells for 3 gp 5 sp), and `pricing.UNLISTED_GP` (1.5 gp, the
ladder's bottom rung that `_tier_base` already gives anything untiered) where none does.
**That 1.5 gp is this app's number, not the book's**: no PF1e rule for an unlisted thing
was found. The buyer's till caps it the way a stall's does. `accept` caps it from below
only.

`judgement.inject_sale` reads a closed sale of a carried thing: the thing named in the
sentence (or, for "It's a deal" with nothing named, in the last few beats), the buyer named
by a word of their name or the one the player is engaged with, and the player's own share
("at 75% of the crate's value") turned into `accept` against the engine's own value. An
offer — "I try to sell", "I offer the crate for coin" — to somebody who keeps no counter is
a haggle and moves nothing; to a keeper it is a sale (Circle's keeper buys what it is
offered). The 2026-10-03 haggle now sells the crate on turn 94, "I agree to sell…", for
7 sp 5 cp, where the player's 75% would have been 1 gp 1 sp 2 cp.

**Coin is money.** "the coins", "the payment", "the money" (and not "the lead coin", a
token) go through `Engine._give_money`, never into the goods. The amount is the records':

- coin in a container or a pile is emptied into the purse (Circle's money object), the
  empty pouch staying in the pack;
- a payment made to the player within the hour (`Engine._mark_payment`, a props record
  the save keeps, written by every sale) is already in the purse, and the tell says so —
  on the 2026-10-03 save "I take the pouch and count the coins", "I pocket the coins" and
  "I transfer the coins from the pouch" would otherwise each have paid again;
- with no record at all, one copper piece, once an hour: the one coin the engine can
  vouch for, not a model's count (law 3). Sam's pocketed coin (2026-09-30) is in the purse
  now, not in the goods.

Coin set down lies as a pile holding its amount (it used to vanish), and `coin_named` no
longer reads "gold ring" as a gold piece.

**Words that send a thing somewhere.** `judgement.declare_emptying` reads "I transfer the
coins from the pouch into my coin purse" as coin out of the pouch and into the purse;
`judgement.declare_drop` reads "I drop the Brunt of the weight on the ground" as a give
from the player to nobody — to the floor — and replaces whatever give the plan made of it.
`inject_payment` no longer turns coin coming IN into a payment going out.

**Figures of speech.** `_NOT_A_THING` gains brunt, wink, smile, nod and the other faces
and gestures; `_is_a_thing` reads the head before "of". A hand-over the reading never read
(`interpret.hands_nothing`) of a thing the player does not carry is not planned; a carried
thing's hand-over still stands, which keeps the 2026-09-27 ruling in `test_pick_a_fight`.

**Nothing moved, nothing remembered.** A give from somebody who does not have the thing
is a refusal (`status: refused`), and the ledger's item lines (`ledger._moved`) skip
refusals and moves of nothing. They say what moved and between whom — "you sold the crate
to the clerk of the counting house", "you handed the lantern to the smith", "you emptied
the pouch into the purse" — with no price, because the ledger holds no digit (its own
rule); the price is the tell's: "Kesst Vayr sells the crate to the clerk of the counting
house for 7 silver pieces, 5 copper pieces."

## A take named in words (2026-10-08)

Measured by the deeds lane with the local model, in 0.2.11, and reproduced with the live
reader and planner before the fix: "I take an apple from the fruit seller without paying"
came out as "the fruit seller hands Kesst Vayr apple", nothing stolen; "another apple" and
"one of the apples" missed the seller's "apple" line, she kept every apple and one was
minted; "…and walk off" walked Kesst out of town.

- **The one acting is the taker.** A `give` with `from_` a person, made by the one who
  ends up holding it, is a take (`Engine._op_give`'s `taking`): the owner is kept and
  `stolen` set, as the holder search already did. A price is consent; so is the holder
  being the actor (Inform's giving action, the rule above read the other way); a
  companion's pack is the party's. The dead own nothing: taken from a body, it is the loot
  op's rule, told as "from the dead thug's body".
- **What they carry, never a new thing.** A take from a person resolves against that
  person's own goods, shelf, weapons and label (`Engine._carried_by`, `holding.named_among`:
  the holder's names matched whole-word inside the words), and a thing they do not carry
  is refused. The open-pockets rule stays for a holder who hands a thing over.
- **Offered or taken is asked, once.** Whether the holder agreed is in the beat before the
  words, not in them, so a take from a person is put to one enum question with the last
  beat shown (`interpret.confirm_take`, `acts_to_ops.confirm_takes`): "offered" makes the
  holder the actor. 16 of 16 on lines written apart from its demonstrations. A `steal` is
  never asked, and out of a fight is built as the same take (in a fight it is the
  manoeuvre).
- **A bare "walk off" under the sky owes no road out** (`interpret._leaving`).

## Replayed on the owner's save

The recorded turns of `items/slice.json`, from an empty pack, through the item stages of
the chain (the model's own intents, the recorded reading, every injector from
`declare_emptying` to `inject_goods`, then the engine):

| | goods | purse |
|---|---|---|
| as saved | brunt of the weight, crate, pouch, coins | empty |
| the base commit, replayed | brunt of the weight, crate, pouch, coins (the smith holds a copy) | empty |
| this branch, replayed | pouch | 7 sp 5 cp (the clerk holds the crate) |

The replay runs the counting-house turns at midday. At the save's own clock (01:20) the
counting house is shut by `keepers` hours, the sale is refused with "not open yet; it
opens at first light", the crate stays in the pack and the purse holds one copper. The
narration had the clerk at his counter at that hour; whether he should be is Lane B's
(time of day), not this lane's.

## Not done

- **The crate was never the docks man's on record.** The narration put it in his hands
  (turn 46) and the player's words then took "the brunt of the weight", not the crate; the
  engine only knows a person holds a thing from their goods or their label. Grounding a
  thing the PROSE puts in somebody's hands needs the prose read for things the way
  `seen-people` reads it for people. Logged, not built.
- **No reaction to a theft.** `stolen` is recorded; nobody notices it yet.
- **Trade goods at full value** (PF1e p.140) needs a trade-goods table; nothing here
  lists one, so a sack of grain sells at half like anything else.
- **Putting a thing INTO a container** ("I put the ring in the pouch") is not read.
