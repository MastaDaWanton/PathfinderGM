# Research note, 2026-11-20: carter-goods lane (playtest items 5, 6, 17)

Branch `fix/carter-goods`. Written before any code, as the lane brief requires. Every quote
below was fetched on 2026-11-20; a claim that could not be fetched is marked **unconfirmed**.

## What the save shows (reproduced from the owner's turn log)

- **#1-#8, item 6.** "inspect his cargo" was read `look`, turned into a browse
  (`interpret.browsed` -> act `buy`), and no counter opened, because the carter is no keeper
  (`play.views._merchant_here`). The first turn's plan wrote `judge item="the carter's cargo"`,
  refused "Shadow is not carrying the carter's cargo", and the narrator wrote "You find no
  items of the carter's to take". The carter (`c2`, a `commoner` block) had empty `goods`,
  `inventory`, `stock` and no `kit_pending`: nothing on record anywhere. The two later beats
  invented the cargo ("Mostly just basic supplies").
- **#17-#23, item 5.** The carter offered "dried meat and some hard bread" from a pack that
  held nothing. "I accept the food" was read `consume: the food`, the plan wrote
  `eat item=trail-rations#1`, and Shadow ate from her own rations (10 -> 9).
- **#98, item 17.** "Taken from clockwork spy: 1 Faerholt platinum piece" at the fight's
  end. The coin is `treasure.worth`: the spy's block prints `treasure: "incidental (gemstone
  worth 50 gp)"`, CR 1/2 -> rung 0 (100 gp), x0.5 incidental x0.25 per creature = 12.5 gp
  centre, rolled to 10 gp, paid as 1 pp. `carried_gp` subtracts nothing because the
  compiled gear row for the gemstone has no key. #133 "I loot the clockwork spy" then found
  nothing, which is right for its pockets.

## Item 17: what a construct carries

**Pathfinder 1e.** Bestiary introduction, Treasure
(https://www.legacy.aonprd.com/bestiary/introduction.html):
- "'None' indicates that the creature normally has no treasure (as is typical for an
  unintelligent creature that has no real lair...)".
- "'Incidental' indicates the creature has half this standard value, and then only within
  the confines of its lair."
- "'NPC gear' indicates the monster has treasure as normal for an NPC of a level equal to
  the monster's CR."

Clockwork spy (Bestiary 3, https://aonprd.com/MonsterDisplay.aspx?ItemName=Clockwork%20Spy):
Treasure "incidental (gemstone worth 50 gp)". The gem is part of the body: Record Audio
stores sound "onto a small gemstone worth 50 gp embedded in its body"; "Removing a gemstone
or installing a gemstone into a clockwork spy requires a DC 25 Disable Device check" (the
critic's re-fetch did not show "as a full-round action": unverified); and self-destruct
"automatically destroys its gemstone, along with any information contained inside it."

**Other traditions.**
- *D&D 3.5 SRD / 1e share the line.* The Pathfinder text above is the 3.5 Monster Manual's
  treasure entry carried over; I did not fetch the 3.5 text separately (**unconfirmed**
  wording match).
- *Lair vs carried treasure.* OSR play splits it the same way: B/X's treasure types give
  each monster an individual type (carried) and a lair type. I did not fetch a primary
  B/X page this session, so this is **unconfirmed** and is not relied on.
- *This codebase already agrees.* `bestiary._carries_no_coin` (2026-11-01, the owner's
  0.2.25 rot grub) reads "none" and "incidental" as no coin on the body, quoting the same
  Bestiary line. `treasure.worth` is the second copy of that rule and was never brought in
  line: the CLAUDE.md "when you fix a rule, grep for every copy of it" failure.

**Chosen.** `treasure.worth` pays nothing on the body for "incidental", the same as
"none". `CLASSES` keeps 0.5 as the book's value for lair treasure, which nothing builds yet.

**Rejected.**
- Paying the 50 gp gemstone at the fight's end: the book makes it a DC 25 Disable Device
  job, and self-destruct destroys it. It is a harvest-shaped act, not a coin
  drop. Not built; listed as an owner call.
- Special-casing constructs by type: the Treasure line decides (an animated object is
  "none", a spy "incidental"), so no type list is needed.

**Seen and left alone.** `treasure.worth` prices "standard" by the creature's own CR,
where the book says "a CR equal to the average party level". Not this lane's item.

## Items 5 and 6: an NPC's goods, gifts, and a carter's cargo

**Pathfinder 1e.**
- CRB Equipment (https://legacy.aonprd.com/coreRulebook/equipment.html): "Cart 15 gp 200
  lbs.", "Wagon 35 gp 400 lbs.", "Rations, trail (per day) 5 sp 1 lb." No cargo capacity
  is printed for either (docs/trade-goods.md found the same).
- Selling: "a character can sell something for half its listed price", and "Trade goods
  are the exception to the half-price rule." That buying is at the listed price is the
  equipment tables' plain reading; no sentence was quoted for it.
- Sleight of Hand (https://www.aonprd.com/Skills.aspx?ItemName=Sleight%20of%20Hand): "If
  you try to take something from a creature, you must make a DC 20 Sleight of Hand check",
  and "The opponent makes a Perception check to detect the attempt". The engine already
  books a take from a person this way (`Engine._op_give` "taking", `trial.report`).
- **No PF1e rule was found for gifts** beyond Diplomacy's request. So the gift question is
  answered from the traditions below.

**Interactive fiction (Inform 7 Standard Rules,
https://ganelson.github.io/inform/standard_rules/actns.html).** Giving has the check rule
"can't give what you haven't got rule": the action stops unless the giver holds the thing,
and the carry-out rule, the "standard giving rule", has the body "move the noun to the
second noun". So a gift is a move from the giver's hands, never a new object. The "block
giving rule" refuses the player's gifts by default ("doesn't seem interested"); gifts
between other people are not blocked.

**MUDs (tbaMUD `src/shop.c`,
https://raw.githubusercontent.com/tbamud/tbamud/master/src/shop.c).**
- `shopping_list()` walks the keeper's own carrying list (`keeper->carrying`). The list a
  player sees IS what the keeper holds.
- `shopping_buy()`: for an item the shop "produces", `read_object()` makes a fresh copy
  (unlimited). For anything else, `obj_from_char(obj)` moves the real object off the
  keeper, so it is sold once. A carter's cart is the second kind: what is on it, once.
- The CircleMUD 2.x shop.doc
  (https://rsync.nic.funet.fi/pub/unix/games/circlemud/docs/2.x/shop.doc): "Shopkeepers
  should be hard (if even possible) to kill. The benefits players can receive from killing
  them is enough to unbalance most non monty-haul campaigns." Reading "the benefits" as
  the stock on the body is my inference; the doc does not say which benefits.

**Roguelikes (NetHack, https://nethackwiki.com/wiki/Shop).** "A shop's inventory consists
of all the items on any square of its floor", and the shopkeeper "owns the shop and its
contents". Picked-up goods carry an "unpaid" tag with the price. Leaving without paying
puts the value on your debt and summons the Kops. Ownership is a fact about the thing,
with theft as its consequence.

**CRPGs.**
- *Baldur's Gate 3 (https://bg3.wiki/wiki/Pickpocketing):* "any item carried by a trader
  can be viewed as an available target for stealing", qualified "In most instances". The
  trader's wares are on the trader. The same page: "Items in the environment which belong to
  another creature are indicated with a red outline and text." (That is about things lying
  in the world, not a trader's inventory.)
- *Skyrim (UESP).* Search snippets of the Merchants and Stores pages say that, outside
  hunters, peddlers and skooma dealers, merchants depend on hidden merchant chests, and
  that vendors also sell from their personal inventory (food, lockpicks, gems). The
  Merchants page itself returned 403, so this rests on the search snippet:
  **partly unconfirmed**. Creation Kit ownership (an owner on each object with a stolen
  flag) is already this app's model (docs/things-and-owners.md).
- *Tried and abandoned?* I looked for a claim that Morrowind kept merchant stock on the
  body and its sequels moved it to chests. I could not confirm it from any page, so it is
  **not used**. The CircleMUD warning above is the nearest sourced concern (with my inference marked).

### What the design takes from this

1. **The wares are on the person, and the list the player sees is that record** (tbaMUD's
   `keeper->carrying`, BG3's traders). The carter's cargo goes into the carter's `goods`,
   the one store the engine's take, hand-over, steal and loot doors already read. A cart
   prop with `contents` (NetHack's floor, Skyrim's chest) was considered and rejected
   below.
2. **Sold once** (tbaMUD's `obj_from_char`). Buying off the carter moves the real line from
   his goods to the buyer, at the book price moved by his terms (`pricing.seller_percent`).
   Nothing restocks.
3. **A gift is a move from the giver's hands** (Inform's "can't give what you haven't got"
   and "move the noun"). Accepting an offered thing is a take from the person who offered
   it. `acts_to_ops.confirm_takes` already asks "offered or taken?" against the last beat,
   so an offered thing is a hand-over and anything else is the existing theft. What was
   missing is that "I accept the food" was read as eating, and that a take naming no
   holder never reached that question.
4. **The narrator is shown what the person carries** (law 3, the "HAS (fact)" line the PC
   already gets), so an offer can only name real things. This is a fact in the brief, not
   an instruction to behave.
5. **Theft keeps the consequences it has everywhere else.** A take from a person is filed
   `took_from`, marked stolen, and booked by the deeds reader with its witnesses. No new
   crime path is added.

### Where the cargo comes from

The opening document (`content/openings/road-starts.json`, `road-in`) names the lead's load
as a table of the CRB's own general goods: a short pack (trail rations, a waterskin) and a
draw from "basic supplies" goods the general store already prices (`goods.GEAR`). Seeded
off the story seed, so a world gets the same carter twice. It is world-agnostic because the
goods are the rulebook's, not any world's. A world-made commodity cart (World Bible's
`trade_routes`, `ships.lading`'s shape) was considered: the opening knows the town, but a
carter on a village road hauling 400 lb of iron reads wrong, and lots in `Scene.cargo` have
no "a person here owns it and sells it" door. Not built.

### Rejected, with reasons

- **The cart as a props container with `contents`.** `_looks_in` would list it for free, but
  a take from a container keeps no owner or `stolen`, a loot of the carter would leave his
  cart's goods behind, and nothing can buy out of a container. Three doors to add against
  one (buy) for goods on the person.
- **Opening the counter's market shelf for the carter** (adding "carter" to `_MERCHANT`). It
  would sell the town's whole general store from a broken cart. That is the "produced,
  unlimited" kind of shop, and a cart is the other kind.
- **A keyword list for "accept".** The fix is the reader's own gloss and one demonstration
  (docs/structured-turn.md: the reader's schema and examples, never a regex). "Accept" maps
  to `take` and the existing closed question decides whether it was offered.
- **Refusing every take from a person** (Inform's and TADS's default). docs/items-have-
  owners.md already refused this, because the narrator stages hand-overs.

### Could not confirm

- Skyrim's merchant-chest rule beyond the search snippet (the UESP page returned 403).
- Any Morrowind -> Oblivion change in where merchant stock lives.
- A Bannerlord "trade with a caravan on the map" option. Searched and not found, not used.

## Second pass

A critic subagent re-fetched all nine cited sources on 2026-11-20. It found no wrong
quote and three imprecisions (Inform's carry-out rule name and the block rule's scope, the
shop.doc paraphrase, an unquoted buying-price line), plus one unverified phrase ("full-round
action"). All four are corrected above. It did not check the Skyrim claims, which were
already marked unconfirmed.
