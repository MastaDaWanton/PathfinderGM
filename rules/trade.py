"""Bulk trade goods: buy a trade route's commodity where it is made, carry it, sell it
where the route says it is wanted (owner, 2026-11-14: "can i purchase bulk trade goods
per the traded commodities from world bible to sell for profit at the destinations
listed?" — "build both"). The design record is docs/trade-goods.md.

**The price is the book's.** A world commodity is free text ("tempered steel", "Turmoil-era
tea blends.") and the book prices none of them, so each is filed under the nearest row of
the Core Rulebook's Trade Goods table (Table 6-3, p.140), with Ultimate Equipment's longer
table for the things the Core one lacks (wool, glass, charcoal), by `ROWS`/`WORDS` below:
an engine table read against the world's export, never a number a model names (law 3).
Trade goods sell "at full value" — the exception to the half-price rule — so a lot sells
at its row's price times the market's standing, not at half.

**The market moves, and recovers** (docs/trade-goods.md, "What the traditions did").
Elite Dangerous shipped unlimited demand for its mining minerals and had to add finite
demand in 2020 (and patch the one mineral that slipped through); Mount & Blade moves the
price with every unit; Patrician anchors a town's price to its stock against about a
week of consumption. So: every unit bought pushes this market's price for the row up,
every unit sold pushes it down, linearly against the market's `volume` (its base value's
worth of the row, the GameMastery settlement figure `market.base_value` already reads),
and the push ebbs back to nothing over `RECOVER_DAYS`. A market cannot sell more than its
stock (`volume` units) nor take more than its appetite. One curve for both directions, so
buying and selling back at one counter nets nothing — the only profit is carrying it.

**Where the goods are** is a state a guard can defend (the hired-swords lane): every lot
is a record in `Scene.cargo` owned by the party, `stowed` with the party (its backs,
beasts and wagon), in a ship's `hold`, `left` at a settlement, or `taken` by whoever
robbed the party (`held_by`, `stolen`). Nothing here reads the player's words.
"""
from __future__ import annotations

import math

# --- the book's rows -------------------------------------------------------------------
#
# key: (name, copper per unit, the unit, pounds per unit, kind).
# Prices: Core Rulebook Table 6-3 "Trade Goods" (legacy.aonprd.com/coreRulebook/
# equipment.html) first; the rows marked UE are Ultimate Equipment's "Trade Goods" table
# (legacy.aonprd.com/ultimateEquipment/gear/entertainmentAndTradeGoods.html), used only
# where the Core table has nothing near. Where the two disagree (UE lists cloves and
# saffron twice) the Core price stands.
#
# Weights are the unit's where the unit IS a weight. Neither table weighs a square yard
# of cloth or a pelt, and both of those weights are THIS APP'S: a square yard of linen
# about half a pound and of silk a quarter (ordinary fabric weights, rounded), leather a
# pound thin and two thick, a pelt two. Livestock walks: a head weighs nothing on a back
# or a wagon. shortcut: a drove needs no drover and eats nothing; upgrade when herding is
# a job (the hired-swords lane's hirelings could drive it).
ROWS: dict[str, tuple[str, int, str, float, str]] = {
    "wheat": ("wheat", 1, "lb", 1.0, "food"),
    "flour": ("flour", 2, "lb", 1.0, "food"),
    "beans": ("beans", 2, "lb", 1.0, "food"),                 # UE
    "cheese": ("cheese", 2, "lb", 1.0, "food"),               # UE
    "potatoes": ("potatoes", 2, "lb", 1.0, "food"),           # UE
    "chicken": ("chickens", 2, "head", 0.0, "livestock"),
    "charcoal": ("charcoal", 3, "20 lb", 20.0, "fuel"),       # UE: 3 cp for 20 lb
    "coal": ("coal", 5, "20 lb", 20.0, "fuel"),               # UE
    "citrus": ("fruit", 3, "lb", 1.0, "food"),                # UE "citrus"
    "nuts": ("nuts", 3, "lb", 1.0, "food"),                   # UE
    "coffee": ("coffee beans", 5, "lb", 1.0, "food"),         # UE
    "sugar": ("sugar", 5, "lb", 1.0, "food"),                 # UE
    "stone": ("masonry stone", 5, "lb", 1.0, "stone"),        # UE
    "iron": ("iron", 10, "lb", 1.0, "metal"),
    "tobacco": ("tobacco", 50, "lb", 1.0, "food"),
    "copper": ("copper", 50, "lb", 1.0, "metal"),
    "thin-leather": ("thin leather", 50, "sq yd", 1.0, "hide"),   # UE
    "cinnamon": ("cinnamon", 100, "lb", 1.0, "spice"),
    "goat": ("goats", 100, "head", 0.0, "livestock"),
    "glass": ("glass", 100, "lb", 1.0, "stone"),              # UE
    "honey": ("honey", 100, "lb", 1.0, "food"),               # UE
    "pepper": ("pepper", 200, "lb", 1.0, "spice"),
    "sheep": ("sheep", 200, "head", 0.0, "livestock"),
    "pig": ("pigs", 300, "head", 0.0, "livestock"),
    "thick-leather": ("thick leather", 300, "sq yd", 2.0, "hide"),  # UE
    "pelt": ("fox pelts", 300, "pelt", 2.0, "hide"),          # UE "fox pelt"
    "linen": ("linen", 400, "sq yd", 0.5, "cloth"),
    "salt": ("salt", 500, "lb", 1.0, "food"),
    "silver": ("silver", 500, "lb", 1.0, "metal"),
    "marble": ("marble", 500, "lb", 1.0, "stone"),            # UE
    "wool": ("wool", 600, "lb", 1.0, "cloth"),                # UE
    "cotton": ("cotton", 800, "lb", 1.0, "cloth"),            # UE
    "silk": ("silk", 1000, "sq yd", 0.25, "cloth"),
    "cow": ("cattle", 1000, "head", 0.0, "livestock"),
    "chocolate": ("chocolate", 1000, "lb", 1.0, "food"),      # UE
    "saffron": ("saffron", 1500, "lb", 1.0, "spice"),
    "ox": ("oxen", 1500, "head", 0.0, "livestock"),
    "gold": ("gold", 5000, "lb", 1.0, "metal"),
    "platinum": ("platinum", 50000, "lb", 1.0, "metal"),
}

# The world's words for each row, in priority order: the FIRST word of this list found
# in the commodity decides. "Woven Khy'vyr silk" is silk, not linen, because silk comes
# first; "Resonant crystal; high-quality winged livestock" is priced as its crystal.
# `None` is a commodity that is not a bulk good — a service, a contract, a toll, a market
# — or one the book prices on another table (poisons and alchemical goods are formulae,
# rules/alchemist.py; a "wood finish" is a varnish no table lists). Those are never
# offered by the pound: Aurvantis's "mercenary contracts" are hired, not carried.
#
# The nearest-row calls that are judgement rather than a match, said so: ore, steel,
# tools, weapons, clockwork and salvage are iron by the pound (the only base metal under
# copper); gems, pearls, coral and crystal are gold by the pound (the book prices gems
# singly, on the treasure tables, which are not trade goods; gold is the dearest
# non-platinum row); dyes, pigments and inks are pepper (a dear powder by the pound);
# tea is coffee; timber is masonry stone (neither table has wood, and darkwood is a
# magic material); "livestock" unqualified is sheep.
WORDS: tuple[tuple[str, str | None], ...] = (
    # Not bulk goods at all.
    ("contract", None), ("contracts", None), ("contracting", None), ("mercenary", None),
    ("muscle", None), ("toll", None), ("tolls", None), ("service", None),
    ("services", None), ("relay", None), ("market", None), ("logistics", None),
    ("manufacture", None), ("poison", None), ("poisons", None), ("alchemical", None),
    ("explosive", None), ("explosives", None), ("curiosities", None), ("novelty", None),
    ("finish", None), ("finishes", None), ("varnish", None), ("trade", None),
    # Precious.
    ("platinum", "platinum"), ("gold", "gold"), ("silver", "silver"),
    ("copper", "copper"), ("pearl", "gold"), ("pearls", "gold"), ("gem", "gold"),
    ("gems", "gold"), ("gemstone", "gold"), ("gemstones", "gold"), ("jewel", "gold"),
    ("jewels", "gold"), ("coral", "gold"), ("crystal", "gold"), ("crystals", "gold"),
    # Cloth before the words that only say it was worked.
    ("silk", "silk"), ("wool", "wool"), ("woollen", "wool"), ("fleece", "wool"),
    ("fleeces", "wool"), ("cotton", "cotton"), ("linen", "linen"), ("flax", "linen"),
    ("hemp", "linen"), ("fiber", "linen"), ("fibre", "linen"), ("fabric", "linen"),
    ("cloth", "linen"), ("textile", "linen"), ("textiles", "linen"),
    ("starweave", "linen"), ("weave", "linen"), ("woven", "linen"),
    ("pelt", "pelt"), ("pelts", "pelt"), ("fur", "pelt"), ("furs", "pelt"),
    ("leather", "thick-leather"), ("hide", "thick-leather"), ("hides", "thick-leather"),
    # Metal.
    ("iron", "iron"), ("steel", "iron"), ("ore", "iron"), ("metal", "iron"),
    ("metalwork", "iron"), ("ironwork", "iron"), ("tool", "iron"), ("tools", "iron"),
    ("weapon", "iron"), ("weapons", "iron"), ("blade", "iron"), ("blades", "iron"),
    ("clockwork", "iron"), ("salvage", "iron"), ("nails", "iron"),
    # Food and stuff.
    ("salt", "salt"), ("saffron", "saffron"), ("clove", "saffron"), ("cloves", "saffron"),
    ("pepper", "pepper"), ("ginger", "pepper"), ("spice", "pepper"), ("spices", "pepper"),
    ("dye", "pepper"), ("dyes", "pepper"), ("pigment", "pepper"), ("pigments", "pepper"),
    ("ink", "pepper"), ("inks", "pepper"), ("cinnamon", "cinnamon"),
    ("tobacco", "tobacco"), ("tea", "coffee"), ("coffee", "coffee"),
    ("chocolate", "chocolate"), ("honey", "honey"), ("sugar", "sugar"),
    ("glass", "glass"), ("ceramic", "glass"), ("ceramics", "glass"), ("pottery", "glass"),
    ("marble", "marble"), ("stone", "stone"), ("masonry", "stone"), ("timber", "stone"),
    ("wood", "stone"), ("hardwood", "stone"), ("lumber", "stone"),
    ("charcoal", "charcoal"), ("coal", "coal"),
    ("flour", "flour"), ("wheat", "wheat"), ("grain", "wheat"), ("barley", "wheat"),
    ("oats", "wheat"), ("rye", "wheat"), ("crop", "wheat"), ("crops", "wheat"),
    ("fish", "cheese"), ("meat", "cheese"), ("cheese", "cheese"), ("smoked", "cheese"),
    ("fruit", "citrus"), ("citrus", "citrus"), ("nut", "nuts"), ("nuts", "nuts"),
    ("bean", "beans"), ("beans", "beans"), ("potato", "potatoes"),
    ("potatoes", "potatoes"), ("vegetable", "potatoes"), ("vegetables", "potatoes"),
    ("fungus", "potatoes"), ("mushroom", "potatoes"), ("mushrooms", "potatoes"),
    ("cattle", "cow"), ("cow", "cow"), ("cows", "cow"), ("oxen", "ox"), ("ox", "ox"),
    ("pig", "pig"), ("pigs", "pig"), ("swine", "pig"), ("goat", "goat"),
    ("goats", "goat"), ("sheep", "sheep"), ("chicken", "chicken"),
    ("chickens", "chicken"), ("poultry", "chicken"), ("livestock", "sheep"),
)
_RANK = {w: i for i, (w, _k) in enumerate(WORDS)}
_ROW_OF = dict(WORDS)

# How far a market's standing moves the book's price (Kenshi's regional multipliers, kept
# small because the book itself has none): where the good is made it is cheaper, where a
# route carries it it is dearer, anywhere else it is the book's.
SUPPLY_FACTOR = 0.8
DEMAND_FACTOR = 1.25
# A market's whole stock bought moves its price by half again; its whole appetite sold
# moves it down by half (linear in between: Mount & Blade's per-unit drift).
SLOPE = 0.5
# Patrician's anchor: about a week of a town's consumption.
RECOVER_DAYS = 7
# What a party member carries of cargo: what they can add and stay in a light load
# (`defeat.spare_load`), so a merchant on foot is not slowed (the app does not slow a
# heavy load, gear.load's `enforced: False`).
# CRB, Carrying Capacity: "a character can generally push or drag along the ground as
# much as five times his maximum load" — what a team hauls on a cart or a wagon, less
# the vehicle (CRB Table 6-9: cart 200 lb, one beast; wagon 400 lb, two).
DRAG_TIMES = 5
VEHICLES = {"wagon": (400.0, 2), "cart": (200.0, 1)}
# CRB, Carrying Capacity, "Bigger and Smaller Creatures": quadrupeds' multipliers.
QUADRUPED = {"fine": 0.25, "diminutive": 0.5, "tiny": 0.75, "small": 1.0, "medium": 1.5,
             "large": 3.0, "huge": 6.0, "gargantuan": 12.0, "colossal": 24.0}
# Freight in a ship's hold: a ton of it pays what one passenger does (CRB Table 6-9,
# 1 sp a mile a head), by weight. THIS APP'S number — no Pathfinder book prices freight —
# reasoned from the book measuring a hold in tons (CRB: a sailing ship carries 150 tons
# with a crew of 20) and a berth in heads. A berth's rate per 200 lb was tried first and
# priced iron out of the sea altogether: 14.4 cp a pound over 288 miles for a 10 cp good.
FREIGHT_LB_A_FARE = 2000
# A road toll's levy on cargo: a fortieth of its book value (THIS APP'S: medieval tolls
# and customs ran at a fortieth to a tenth ad valorem; the low end, as a toll is the
# decision, `ontheway.TOLL_DICE`, not the sum).
TOLL_SHARE = 1 / 40

PREFIX = "cargo:"


def words_of(text: str) -> list[str]:
    """The commodity's words, lowered, split on everything that is not a letter."""
    out, cur = [], []
    for ch in str(text or "").lower():
        if ch.isalpha():
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out


def row_for(commodity: str) -> str | None:
    """The `ROWS` key a world commodity is priced as, or None when it is not a bulk good
    (or the table has no word for it)."""
    hits = [w for w in words_of(commodity) if w in _RANK]
    if not hits:
        return None
    return _ROW_OF[min(hits, key=_RANK.__getitem__)]


# docs/for-world-bible.md ask 19: a good the world describes in words, `kind` and `worth`,
# lands on the book's row for that pair. Words, never prices (rule 1 of the asks). The
# ladder in each kind climbs the book's own rows; "other" has no row and is not offered.
GOOD_ROWS: dict[tuple[str, str], str] = {
    ("food", "cheap"): "wheat", ("food", "common"): "tobacco", ("food", "dear"): "salt",
    ("food", "precious"): "saffron",
    ("spice", "cheap"): "cinnamon", ("spice", "common"): "pepper",
    ("spice", "dear"): "saffron", ("spice", "precious"): "saffron",
    ("cloth", "cheap"): "linen", ("cloth", "common"): "wool", ("cloth", "dear"): "cotton",
    ("cloth", "precious"): "silk",
    ("hide", "cheap"): "thin-leather", ("hide", "common"): "thick-leather",
    ("hide", "dear"): "pelt", ("hide", "precious"): "pelt",
    ("metal", "cheap"): "iron", ("metal", "common"): "copper", ("metal", "dear"): "silver",
    ("metal", "precious"): "gold",
    ("stone", "cheap"): "stone", ("stone", "common"): "glass", ("stone", "dear"): "marble",
    ("stone", "precious"): "gold",
    ("timber", "cheap"): "stone", ("timber", "common"): "stone", ("timber", "dear"): "glass",
    ("timber", "precious"): "marble",
    ("fuel", "cheap"): "charcoal", ("fuel", "common"): "coal", ("fuel", "dear"): "coal",
    ("fuel", "precious"): "coal",
    ("livestock", "cheap"): "chicken", ("livestock", "common"): "sheep",
    ("livestock", "dear"): "cow", ("livestock", "precious"): "ox",
}
# Ask 20: how much of it moves, as a word, scaling the market's stock and appetite.
VOLUME_WORDS = {"trickle": 0.5, "steady": 1.0, "heavy": 2.0}


def row_of_good(good) -> str | None:
    """The row for a world good: ask 19's `{"kind", "worth", "service"}` when the export
    carries it, else the commodity's words (`row_for`). A `service` is never a good."""
    if isinstance(good, dict):
        if good.get("service"):
            return None
        k = GOOD_ROWS.get((str(good.get("kind") or "").lower(),
                           str(good.get("worth") or "").lower()))
        return k or row_for(str(good.get("name") or ""))
    return row_for(str(good or ""))


def route_row(r: dict, sought: bool = False) -> str | None:
    """The row a trade route carries: its `good` (ask 19) when given, else its
    commodity's words — as the buyer seeks it (`sought_as`) when `sought`."""
    if isinstance(r.get("good"), dict):
        return row_of_good(r["good"])
    return row_for(str((r.get("sought_as") if sought else "") or r.get("commodity") or ""))


def _settlement_goods(s: dict, side: str) -> list:
    """Ask 21's `goods.sells` / `goods.buys` rows when the export carries them, else the
    settlement's one prose line."""
    rows = (s.get("goods") or {}).get(side) if isinstance(s.get("goods"), dict) else None
    if isinstance(rows, list) and rows:
        return [g for g in rows if isinstance(g, dict)]
    return [str(s.get(side) or "")]


def row(key: str) -> dict:
    name, cp, unit, lb, kind = ROWS[key]
    return {"key": key, "name": name, "cp": cp, "unit": unit, "lb": lb, "kind": kind}


# --- what the world says is traded where ------------------------------------------------

def _settlements(world) -> list[dict]:
    return [s for s in ((getattr(world, "play", None) or {}).get("settlements") or [])
            if isinstance(s, dict)]


def _name(world, place_id: str) -> str:
    try:
        ent = world.get(place_id) if world is not None and place_id else None
    except Exception:  # noqa: BLE001 - an unknown id is a nameless place
        ent = None
    return str(getattr(ent, "name", "") or "")


def supplied_at(world, place_id: str) -> dict[str, str]:
    """{row key: the world's own word for it} for what this settlement makes or ships:
    the origin of a trade route, or its `sells` line."""
    out: dict[str, str] = {}
    if world is None or not place_id:
        return out
    for r in getattr(world, "trade_routes", None) or ():
        if r.get("origin_id") == place_id:
            k = route_row(r)
            if k:
                out.setdefault(k, str(r.get("commodity") or ROWS[k][0]))
    for s in _settlements(world):
        if s.get("id") == place_id:
            for g in _settlement_goods(s, "sells"):
                k = row_of_good(g)
                if k:
                    out.setdefault(k, str(g.get("name") if isinstance(g, dict) else g))
    return out


def demanded_at(world, place_id: str) -> set[str]:
    """The row keys this settlement wants: the destination of a route (as the route says
    it is sought), or its `buys` line."""
    out: set[str] = set()
    if world is None or not place_id:
        return out
    for r in getattr(world, "trade_routes", None) or ():
        if r.get("destination_id") == place_id:
            k = route_row(r, sought=True)
            if k:
                out.add(k)
    for s in _settlements(world):
        if s.get("id") == place_id:
            out |= {k for k in map(row_of_good, _settlement_goods(s, "buys")) if k}
    return out


def sells_dear_in(world, key: str, origin: str = "") -> list[str]:
    """The names of the settlements that want `key`: this origin's own routes first (the
    destinations listed), then any other that demands it. Sorted within each."""
    if world is None:
        return []
    own, other = set(), set()
    for r in getattr(world, "trade_routes", None) or ():
        dest = str(r.get("destination_id") or "")
        if dest and route_row(r, sought=True) == key:
            (own if r.get("origin_id") == origin else other).add(dest)
    for s in _settlements(world):
        if key in map(row_of_good, _settlement_goods(s, "buys")):
            other.add(str(s.get("id") or ""))
    other -= own | {origin}
    names = lambda ids: sorted(n for n in (_name(world, i) for i in ids) if n)  # noqa: E731
    return names(own) + names(other)


def standing(world, place_id: str, key: str) -> str:
    """"supply", "demand" or "" — supply wins where a place both makes and wants a thing,
    since it is then not short of it."""
    if key in supplied_at(world, place_id):
        return "supply"
    return "demand" if key in demanded_at(world, place_id) else ""


def factor_of(stand: str) -> float:
    return {"supply": SUPPLY_FACTOR, "demand": DEMAND_FACTOR}.get(stand, 1.0)


# --- the market's stock and appetite ---------------------------------------------------

def volume(world, place_id: str, key: str) -> int:
    """How many units this market holds of the row and takes of it: its base value's worth
    (`market.base_value`, the GameMastery/Ultimate Campaign settlement figure), a town's
    where the world gives no size. At least one."""
    from . import market

    gp = market.base_value(market.scale_here(world, place_id)) or market.BASE_VALUE_GP["town"]
    # Ask 20: a route that says how much moves along it scales the ends it touches.
    said = [VOLUME_WORDS[str(r.get("volume")).lower()]
            for r in getattr(world, "trade_routes", None) or ()
            if str(r.get("volume") or "").lower() in VOLUME_WORDS
            and place_id in (r.get("origin_id"), r.get("destination_id"))
            and route_row(r) == key]
    return max(1, int(gp * 100 * (max(said) if said else 1.0) // max(1, ROWS[key][1])))


def _day(scene) -> int:
    return int(getattr(scene, "clock_minutes", 0) or 0) // (24 * 60)


def pressure(scene, place_id: str, key: str, vol: int) -> float:
    """The units this market is up (+, bought from it) or down (-, sold to it) today,
    after the days since have ebbed it back by `vol / RECOVER_DAYS` a day."""
    rec = (getattr(scene, "trade_pressure", None) or {}).get(f"{place_id}|{key}")
    if not rec:
        return 0.0
    net = float(rec.get("net", 0) or 0)
    ebb = vol * max(0, _day(scene) - int(rec.get("day", 0) or 0)) / RECOVER_DAYS
    return max(0.0, net - ebb) if net > 0 else min(0.0, net + ebb)


def _press(scene, place_id: str, key: str, vol: int, units: float) -> None:
    net = pressure(scene, place_id, key, vol) + units
    scene.trade_pressure[f"{place_id}|{key}"] = {"net": round(net, 3), "day": _day(scene)}


def can_buy(scene, world, place_id: str, key: str) -> int:
    """Units this market still has to sell today."""
    vol = volume(world, place_id, key)
    return max(0, int(vol - pressure(scene, place_id, key, vol)))


def can_sell(scene, world, place_id: str, key: str) -> int:
    """Units this market will still take today."""
    vol = volume(world, place_id, key)
    return max(0, int(vol + pressure(scene, place_id, key, vol)))


def book_cp(scene, world, place_id: str, key: str, units: int, buying: bool) -> int:
    """The copper for `units` of the row at this market, the curve integrated across
    them (the average of the first and last unit's price, exact for a straight line), so
    two small trades cost what one big one does. Before anybody's terms."""
    vol = volume(world, place_id, key)
    net = pressure(scene, place_id, key, vol)
    mid = net + units / 2 if buying else net - units / 2
    each = ROWS[key][1] * factor_of(standing(world, place_id, key)) * (1 + SLOPE * mid / vol)
    total = max(0.0, each) * units
    return int(math.ceil(round(total, 6))) if buying else int(math.floor(round(total, 6)))


def unit_now(scene, world, place_id: str, key: str) -> float:
    """What the next unit costs here, in copper, before terms: for the panel's line."""
    vol = volume(world, place_id, key)
    return ROWS[key][1] * factor_of(standing(world, place_id, key)) \
        * (1 + SLOPE * pressure(scene, place_id, key, vol) / vol)


def record(scene, world, place_id: str, key: str, units: int, buying: bool) -> None:
    _press(scene, place_id, key, volume(world, place_id, key),
           units if buying else -units)


# --- the lots --------------------------------------------------------------------------

def lots(scene) -> list[dict]:
    return getattr(scene, "cargo", None) or []


def where_now(scene, lot: dict) -> str:
    """The location id the lot is at: the party's for one stowed with them, the ship's
    for one in a hold (a docked ship is at her port), its own for one left or taken."""
    stowed = lot.get("stowed")
    if stowed == "party":
        return str(getattr(scene, "location_id", "") or "")
    if stowed == "hold":
        ship = next((v for v in getattr(scene, "vessels", None) or ()
                     if str(v.get("id")) == lot.get("vessel")), None)
        return str((ship or {}).get("at") or lot.get("vessel") or "")
    return str(lot.get("at") or "")


def reachable(scene, key: str = "") -> list[dict]:
    """The party's own lots it can trade from where it stands (not a robber's)."""
    here = str(getattr(scene, "location_id", "") or "")
    return [x for x in lots(scene) if x.get("stowed") != "taken"
            and (not key or x.get("key") == key) and where_now(scene, x) == here]


def lb_of(lot: dict) -> float:
    return round(float(lot.get("units", 0)) * ROWS[lot["key"]][3], 2)


def with_party_lb(scene) -> float:
    return round(sum(lb_of(x) for x in lots(scene) if x.get("stowed") == "party"), 2)


def add_lot(scene, key: str, units: int, owner: str, paid_cp: int, bought_at: str,
            commodity: str = "") -> dict:
    """The party's new lot, merged into one of the same row already stowed with them."""
    lot = next((x for x in lots(scene) if x.get("key") == key and x.get("stowed") == "party"
                and x.get("owner") == owner), None)
    if lot is None:
        n = 1 + max((int(str(x.get("id", "lot-0"))[4:] or 0) for x in lots(scene)
                     if str(x.get("id", "")).startswith("lot-")), default=0)
        lot = {"id": f"lot-{n}", "key": key, "name": ROWS[key][0], "units": 0,
               "paid_cp": 0, "owner": owner, "stowed": "party", "bought_at": bought_at,
               "commodity": commodity or ROWS[key][0]}
        scene.cargo.append(lot)
    lot["units"] = int(lot["units"]) + int(units)
    lot["paid_cp"] = int(lot.get("paid_cp", 0)) + int(paid_cp)
    return lot


def take_units(scene, key: str, units: int) -> tuple[int, int]:
    """Take `units` of the row out of the party's reachable lots: (taken, what they cost
    the party, pro rata). Emptied lots are removed."""
    taken = paid = 0
    for lot in reachable(scene, key):
        if taken >= units:
            break
        n = min(int(lot["units"]), units - taken)
        share = int(round(int(lot.get("paid_cp", 0)) * n / max(1, int(lot["units"]))))
        lot["units"] -= n
        lot["paid_cp"] = int(lot.get("paid_cp", 0)) - share
        taken, paid = taken + n, paid + share
    scene.cargo = [x for x in lots(scene) if int(x.get("units", 0)) > 0]
    return taken, paid


# --- how much the party can haul -------------------------------------------------------

def _beast_heavy(a) -> float:
    from . import gear

    try:
        strength = int(a.ability_score("str"))
    except Exception:  # noqa: BLE001 - an unreadable block hauls what a Str 10 does
        strength = 10
    size = str(getattr(a, "size", "large") or "large").lower()
    return gear.capacity(strength, "medium")[2] * QUADRUPED.get(size, 3.0)


def haul_lb(scene) -> dict:
    """{"lb", "how"}: the pounds of cargo the party can take on the road, and in words how.

    Every walker (the PC, anybody travelling with them who is not a mount) adds their
    spare light load; a cart or wagon carried in anybody's goods is hitched to the
    strongest beasts it needs and hauls five times their heavy load less its own weight;
    every other beast carries its heavy load. shortcut: a pack animal needs no pack
    saddle here (the CRB's saddle "holds as much gear as the mount can carry"); upgrade
    if the stables' tack should matter."""
    from . import defeat, journey, states

    beasts = journey.owned_mounts(scene)
    beast_refs = {b.ref for b in beasts}
    walkers = [a for a in (getattr(scene, "people", {}) or {}).values()
               if a.ref not in beast_refs and not a.has_state("state.down.dead")
               and (a.is_pc or a.has_state(states.TRAVELS_WITH_YOU))]
    lb = sum(defeat.spare_load(a) for a in walkers)
    how = ["on your backs"] if lb else []
    heavy = sorted((_beast_heavy(b) for b in beasts), reverse=True)
    held = {str(k).lower() for a in walkers for k, n in (a.goods or {}).items()
            if int(n or 0) > 0}
    # The stables' tack is delivered to the satchel (`goods.deliver`), under its name.
    held |= {str(getattr(x, "base", "") or "").lower() for a in walkers
             for x in (getattr(a, "stock", None) or {}).values()
             if int(getattr(x, "count", 0) or 0) > 0}
    for vehicle, (weight, team) in VEHICLES.items():
        if vehicle in held and len(heavy) >= team:
            pulled = DRAG_TIMES * sum(heavy[:team]) - weight
            if pulled > 0:
                lb += pulled
                heavy = heavy[team:]
                how.append(f"a {vehicle}")
            break
    if heavy:
        lb += sum(heavy)
        how.append(f"{len(heavy)} pack beast{'s' if len(heavy) != 1 else ''}")
    return {"lb": round(lb, 1), "how": how}


def _split(scene, lot: dict, units: int) -> dict:
    """Part `units` off `lot` into a new lot of the same row and owner, its share of the
    cost going with it. Returns the new lot."""
    share = int(round(int(lot.get("paid_cp", 0)) * units / max(1, int(lot["units"]))))
    n = 1 + max((int(str(x.get("id", "lot-0"))[4:] or 0) for x in lots(scene)
                 if str(x.get("id", "")).startswith("lot-")), default=0)
    new = {**lot, "id": f"lot-{n}", "units": int(units), "paid_cp": share}
    lot["units"] = int(lot["units"]) - int(units)
    lot["paid_cp"] = int(lot.get("paid_cp", 0)) - share
    scene.cargo.append(new)
    return new


def load_up(scene) -> tuple[list[str], list[str]]:
    """Fill the party's backs, beasts and wagon from its lots here — what it already
    carries first, then what it left here — splitting a lot where only part of it fits,
    and set the rest down here. (what was taken up, what stays here), in words. A row
    that walks (livestock) always goes."""
    here = str(getattr(scene, "location_id", "") or "")
    room = haul_lb(scene)["lb"]
    pool = ([x for x in lots(scene) if x.get("stowed") == "party"]
            + [x for x in lots(scene) if x.get("stowed") == "left" and x.get("at") == here])
    was = {id(x): x.get("stowed") for x in pool}
    up, left = [], []
    for lot in pool:
        each = ROWS[lot["key"]][3]
        fit = int(lot["units"]) if each <= 0 else min(int(lot["units"]),
                                                       int((room + 1e-9) // each))
        if 0 < fit < int(lot["units"]):
            rest = _split(scene, lot, int(lot["units"]) - fit)
            rest["stowed"], rest["at"] = "left", here
            left.append(said(rest))
        if fit > 0:
            room -= fit * each
            lot["stowed"] = "party"
            lot.pop("at", None)
            if was[id(lot)] == "left":
                up.append(said(lot))
        else:
            lot["stowed"], lot["at"] = "left", here
            left.append(said(lot))
    _merge(scene)
    return up, left


def said(lot: dict) -> str:
    """"120 lb of salt", "6 head of cattle", "40 sq yd of silk"."""
    _n, _cp, unit, _lb, _kind = ROWS[lot["key"]]
    n = int(lot.get("units", 0))
    if unit == "20 lb":
        return f"{n * 20} lb of {lot['name']}"
    if unit == "pelt":
        return f"{n} {lot['name']}" if n != 1 else f"1 {lot['name'].rstrip('s')}"
    return f"{n} {unit} of {lot['name']}"


# --- freight, tolls, losses ------------------------------------------------------------

def freight_cp(lb: float, miles: int) -> int:
    """The freight on `lb` pounds over `miles`, in copper, before anybody's terms."""
    from . import ships

    if lb <= 0:
        return 0
    return int(math.ceil(ships.fare_cp(miles, 1) * float(lb) / FREIGHT_LB_A_FARE))


def shipping(scene) -> list[dict]:
    """The lots a ship booked here would take: the party's own and what they left here."""
    here = str(getattr(scene, "location_id", "") or "")
    return [x for x in lots(scene)
            if x.get("stowed") == "party" or (x.get("stowed") == "left" and x.get("at") == here)]


def _merge(scene) -> None:
    """One lot per row, owner and place: two buys of iron in one hold are one lot."""
    out: list[dict] = []
    for lot in lots(scene):
        twin = next((x for x in out if all(x.get(k) == lot.get(k) for k in
                                            ("key", "owner", "stowed", "at", "vessel",
                                             "held_by"))), None)
        if twin is None:
            out.append(lot)
        else:
            twin["units"] = int(twin["units"]) + int(lot["units"])
            twin["paid_cp"] = int(twin.get("paid_cp", 0)) + int(lot.get("paid_cp", 0))
    scene.cargo = out


def into_hold(scene, vessel_id: str) -> list[str]:
    for lot in shipping(scene):
        lot["stowed"], lot["vessel"] = "hold", vessel_id
        lot.pop("at", None)
    _merge(scene)
    return [said(x) for x in lots(scene)
            if x.get("stowed") == "hold" and x.get("vessel") == vessel_id]


def unload(scene, vessel_id: str, port: str) -> list[str]:
    """She makes port: her hold's lots of the party's are set on the quay at `port`."""
    out = []
    for lot in lots(scene):
        if lot.get("stowed") == "hold" and lot.get("vessel") == vessel_id:
            lot["stowed"], lot["at"] = "left", port
            lot.pop("vessel", None)
            out.append(said(lot))
    return out


def lost_with(scene, vessel_id: str) -> list[str]:
    """She goes down: everything in her hold goes with her."""
    gone = [said(x) for x in lots(scene)
            if x.get("stowed") == "hold" and x.get("vessel") == vessel_id]
    scene.cargo = [x for x in lots(scene)
                   if not (x.get("stowed") == "hold" and x.get("vessel") == vessel_id)]
    return gone


def book_value_cp(lots_: list[dict]) -> int:
    return sum(int(x.get("units", 0)) * ROWS[x["key"]][1] for x in lots_)


def toll_cp(scene) -> int:
    """The levy a toll-keeper asks on what the party is carrying: `TOLL_SHARE` of its book
    value, in copper; 0 for a party carrying no cargo."""
    owned = [x for x in lots(scene) if x.get("stowed") == "party"]
    return int(math.ceil(book_value_cp(owned) * TOLL_SHARE)) if owned else 0


def robbed(scene, robber_ref: str) -> list[str]:
    """The party is beaten where its cargo is: whatever of it is in reach (stowed with
    them, or in the hold of the ship they are on) goes with the robbers, still the
    party's by right (`owner`) and marked stolen — the props ledger's rule
    (docs/items-have-owners.md). shortcut: nothing yet brings a taken lot back when the
    robber is beaten; upgrade with the robbery quest (`defeat.settle`)."""
    here = str(getattr(scene, "location_id", "") or "")
    out = []
    for lot in lots(scene):
        if lot.get("stowed") in ("party", "hold") and where_now(scene, lot) == here:
            lot["stowed"], lot["held_by"], lot["stolen"] = "taken", robber_ref, True
            lot["at"] = here
            lot.pop("vessel", None)
            out.append(said(lot))
    return out


def where_said(scene, world, lot: dict) -> str:
    stowed = lot.get("stowed")
    if stowed == "party":
        return "with you"
    if stowed == "hold":
        ship = next((v for v in getattr(scene, "vessels", None) or ()
                     if str(v.get("id")) == lot.get("vessel")), None)
        return f"in the hold of {(ship or {}).get('name') or 'the ship'}"
    if stowed == "taken":
        return "taken by robbers"
    return f"left at {_name(world, str(lot.get('at') or '')) or 'the quay'}"
