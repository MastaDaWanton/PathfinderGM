# Trade goods: buy where it is made, sell where it is wanted

Owner, 2026-11-14: "can i purchase bulk trade goods per the traded commodities from world
bible to sell for profit at the destinations listed?" and then "build both". Branch
`feat/trade-goods`. The code is `rules/trade.py`; tests are `tests/test_trade_goods.py`.

Before this:
- World Bible's `trade_routes[]` were loaded and fed only `rules/residency.py`.
- A settlement's `sells` line only flavoured a keeper's occupation.
- A crate of cargo nobody priced fell to `pricing.UNLISTED_GP`, 1.5 gp whatever it was.
- A ship carried passengers and nothing else.

## What the rules and the traditions say (researched before designing)

Searched 2026-11-14. Primary sources where they could be had. A claim marked
*unconfirmed* rests on a fan wiki or forum excerpt.

**Pathfinder 1e.**
- *The table.* Core Rulebook Table 6-3, Trade Goods (p.140), priced by the pound, the
  head or the square yard. Ultimate Equipment's longer table adds wool, cotton, glass,
  charcoal, coal, stone, honey, pelts and leather. Sources:
  legacy.aonprd.com/coreRulebook/equipment.html and
  legacy.aonprd.com/ultimateEquipment/gear/entertainmentAndTradeGoods.html.
- *Full value.* "Trade goods are the exception to the half-price rule": they change hands
  "almost as if it were cash itself".
- *No bargaining.* Ultimate Campaign p.139 exempts trade goods from bargaining. The same
  book (p.138) keeps the half-price rule so players cannot outgrow wealth-by-level "by
  buying low and selling high" (aonprd.com/Rules.aspx?ID=1339).
- *Not found.* No official PF1e rule for speculative trade or regional prices. Ultimate
  Campaign's kingdom Trade Edicts pay in build points, not prices. The regional layer
  below is this app's.
- *Vehicles.* Cart 15 gp, 200 lb, one beast. Wagon 35 gp, 400 lb, two beasts. Neither
  is given a cargo capacity. Carrying Capacity: a creature can drag five times its
  maximum load, and quadrupeds carry more than bipeds.
- *Ships.* Ship holds are measured in tons (a sailing ship 150, a keelboat 40–50). No
  book prices freight.

**Trading games.**
- *Elite (1984).* Rerolls a market on every arrival; your own trades do not move it
  (elite.bbcelite.com, market deep dive).
- *Elite Dangerous* shipped unlimited demand at high prices for its mining minerals, and
  the January 2020 update added finite demand that "offers less as demand is met".
  Low-temperature diamonds escaped the change, and Update 1.46 fixed their demand not
  dropping as players sold. Its 1.02 per-player allocation of rare goods was resented as
  arbitrary.
- *Mount & Blade.* Moves the price with every unit: Warband's sixth unit sold in a row
  is 10–15% down (*unconfirmed*). Bannerlord's 2019 blog keeps per-transaction pricing,
  and dropped villages consuming a fixed share "without taking scarcity into account".
- *Patrician / Port Royale.* Anchor a town's price to its stock against about a week of
  its consumption (*unconfirmed*: community sources only).
- *Sid Meier's Pirates! (2004).* Caps what a port's merchant can buy by the gold they
  have on hand.
- *Kenshi.* Multiplies base prices by a regional trade culture (*unconfirmed*: forum).
- *Daggerfall.* Has no commodity trade at all.
- *Not found* for any of these games: recovery rates measured in days.

**What was adopted, and why.**
1. **The book's row, chosen by an engine table.**
   - `trade.WORDS` files a world commodity under the nearest Core or UE row by the first
     of its words in a priority list. "Woven Khy'vyr silk" is silk; "tempered steel" is
     iron; "mercenary contracts", "river tolls" and "poisons" are not bulk goods.
   - No model ever names a price (law 3).
   - The judgement calls are stated in the code: steel and ore count as iron; gems,
     pearls and coral as gold by the pound; dyes as pepper; tea as coffee; timber as
     masonry stone.
2. **Full value, moved by the market's standing.**
   - The book's price ×0.8 where the world says the good is made (a route's origin, or
     the settlement's `sells`).
   - ×1.25 where a route carries it (its destination, or the settlement's `buys`).
   - ×1 anywhere else.
   - Kenshi's regional multipliers, kept small because the book has none.
3. **Every unit moves the price, and the market comes back.**
   - Each unit bought pushes this market's price for the row up; each unit sold pushes
     it down. The push is linear against the market's `volume`: its settlement base value
     (`market.base_value`) worth of the row.
   - The push ebbs back to nothing over `RECOVER_DAYS = 7`, Patrician's week.
   - A market cannot sell more than its stock nor take more than its appetite.
   - Buying and selling use one curve, integrated across the units. So a round trip at one
     counter nets nothing, and two small trades cost what one big one does. The only profit
     is in carrying the goods, which is the point.
   - This is the Elite Dangerous lesson, built in from the start rather than patched in.
4. **No per-player allocation.**
   - Elite's was resented. The limits here are the world's own: the market's stock, its
     appetite, what the party can haul, and the week it takes to refill.
5. **The seller still matters, but the haggle does not.**
   - Prices move with the seller's attitude and thrift (`pricing.seller_percent`), like
     every price since 0.3.2/0.3.3, and with the watch's markup.
   - The day's haggle is not read, because Ultimate Campaign exempts trade goods from
     bargaining.

## Weight is real

A lot weighs what its row says. The book weighs pounds; cloth and pelts are this app's
weights, stated in `trade.ROWS`. Livestock walks.

`trade.haul_lb` is what the party can take on the road:
- every walker's spare light load (`defeat.spare_load`);
- a cart or wagon (now sold at the stables, CRB prices) hitched to the strongest beasts.
  It hauls five times their heavy load, less the vehicle;
- every other beast's heavy load, on the quadruped table.

What does not fit is not refused. It waits `left` at the market, for a second trip or a
ship's hold. Setting out on a road loads what fits and says what stays (`trade.load_up`).

## Where the goods are

Each lot in `Scene.cargo` records:
- `owner`: the PC's ref;
- `stowed`: `party` (with them), `hold` (`vessel`), `left` (`at`) or `taken`
  (`held_by`, `stolen`);
- its units and what it cost.

The hired-swords lane's guards defend a lot by these fields. Nothing here builds hiring.

- **Freight.** A berth booked with cargo charges freight in the same quote the exits row
  shows (`Engine.passage_quote`). A ton pays what one passenger does.
  - This is THIS APP'S number. It comes from the book measuring holds in tons and berths
    in heads.
  - A berth's rate per 200 lb was tried first. It priced iron out of the sea: 14.4 cp a
    pound over 288 miles, for a 10 cp good.
  - When the ship makes port, the hold is swung onto the quay.
- **The wreck** takes the hold with the ship (`Engine._wreck`).
- **Robbers** who beat the party down take the cargo in reach: with the party, or in the
  hold of the ship it is on. It stays the party's by right and is marked stolen
  (`defeat.aftermath`).
- **A road toll-keeper** names a levy on the cargo, a fortieth of its book value. This is
  THIS APP'S number, the low end of medieval ad valorem tolls. It is paid, or gone round,
  like the toll itself.

## Refused, with reasons

- **The basket.** The trade window's basket prices a line as count × price, which is wrong
  when every unit moves the price. Bulk goods are bought a line at a time, and the engine
  states the total.
- **Speculation everywhere.** Only goods the world says a place makes are offered there.
  Anywhere sells at full value.
- **Elite (1984)'s reroll on arrival.** It makes a market a slot machine, and the price no
  longer answers to what the party did.

## What is not done

- A stolen lot does not come back when its robber is beaten (`trade.robbed` says so).
  The robbery quest could carry it.
- Herding livestock costs nothing and needs no drover.
- A pack animal needs no pack saddle.
- Towns charge no customs at their gates.
- Asks 19–21 in docs/for-world-bible.md would replace the word table with the world's own
  words. The readers exist (`trade.route_row`, `row_of_good`, `volume`).
