"""What a character is carrying, and what money is called where they are standing.

Two problems that turn out to be one. A game had run fifty-four turns in which the GM
narrated a pouch of lucite crystals, a cloth, a bed and a woman on it, and emitted
`narrate_only` fifty-four times: not one of those things existed anywhere the engine
could see them. Nothing could be spent, dropped, stolen or counted, because there was
nowhere for a thing to be.

**Goods are open, and honestly so.** A character may carry anything the fiction hands
them. Where the name matches something in the Core tables the engine knows what it is
and says so; where it does not, the item is still carried, still counted, still lost
when it is spent — it simply has no mechanics, and `describe` says that out loud rather
than implying the engine understands a "lucite crystal". Refusing unknown items would
mean the GM could never give the player anything the rulebook did not print, which is
most of what a game is made of.

**Money is 1e underneath and the world's own on the surface.** The ratios are the Core
Rulebook's — 10 copper to a silver, 10 silver to a gold, 10 gold to a platinum — because
every price in the shipped tables is denominated in them and a world that renamed the
maths would have a longsword cost the wrong number. Only the names change, and they are
read from the world where the world says, and coined from the world's own vocabulary
where it does not. A coined name is flagged as coined; nothing here pretends World Bible
wrote a currency it never wrote.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .tables import ARMOUR, SHIELDS

# Core Rulebook Table 6-1, in copper. The ids are the ones the price tables use.
DENOMINATIONS: tuple[tuple[str, int], ...] = (
    ("cp", 1), ("sp", 10), ("gp", 100), ("pp", 1000),
)
METALS = {"cp": "copper", "sp": "silver", "gp": "gold", "pp": "platinum"}

CURRENCY_KEYS = ("Currency", "Coinage", "Money", "Mint", "Economy", "Trade")
# Facts that name a people or a house are the honest place to take a coin's name from.
# A currency called after nothing is the app inventing a proper noun, which is the one
# thing `CLAUDE.md` is most insistent about.
CULTURE_KEYS = ("Social Classes", "Formal Power", "Governance", "Urban Life")

_NAME = re.compile(r"\b([A-Z][\w'’-]{2,})")


@dataclass(frozen=True)
class Coin:
    id: str
    name: str
    copper: int
    coined: bool = False       # True when this app made the name up from world material

    @property
    def plural(self) -> str:
        return self.name + ("es" if self.name.endswith(("s", "x", "ch")) else "s")


def _proper_noun(world, place) -> str:
    """A name the world already uses, to hang a coin on. "" when there is none."""
    for source in (place, None):
        facts = getattr(source, "facts", {}) if source is not None else {}
        for key in CULTURE_KEYS:
            for found in _NAME.findall(str(facts.get(key, ""))):
                if found.lower() not in ("the", "and", "with"):
                    # The stem, not the compound. "Khy'vyr-centric clans" names the
                    # Khy'vyr; a coin called the "Khy'vyr-centric copper piece" is the
                    # app mistaking an adjective for a people.
                    return found.split("-")[0]
    for group in (getattr(world, "factions", None) or []):
        name = str(group.get("name", "")).strip()
        if name:
            # "The Guild of Saltmakers' Sons" -> "Saltmakers'". The article and the
            # common nouns carry no identity; the first capitalised word after them does.
            for found in _NAME.findall(name):
                if found.lower() not in _NOT_A_PEOPLE:
                    return found
    return ""


# Words that are capitalised in a faction's name without naming anybody. "The Order of
# the Winged Scales" yielded "Winged", and a "Winged gold piece" is this app mistaking
# an adjective for a people — the same error the hyphen strip above exists to prevent.
_NOT_A_PEOPLE = {
    "the", "of", "and", "guild", "order", "conclave", "cooperative", "company",
    "council", "circle", "league", "house", "clan", "sons", "daughters", "scales",
    "winged", "aerial", "royal", "grand", "high", "old", "new", "great", "free",
    "silent", "golden", "silver", "iron", "black", "white", "red", "first", "last",
}


def _stated_currency(world, place) -> str:
    """A currency the export actually names, if it does. Nothing here guesses."""
    for source in (place, None):
        facts = getattr(source, "facts", {}) if source is not None else {}
        for key in CURRENCY_KEYS:
            value = str(facts.get(key, "")).strip()
            m = re.search(r"\b([A-Z][\w'’-]{2,})\s+(?:mark|crown|piece|coin|penny|"
                          r"shilling|florin|ducat|talent)s?\b", value)
            if m:
                return m.group(0)
    return ""


def coinage(world=None, place=None) -> list[Coin]:
    """What the money is called here, cheapest first.

    Falls all the way back to the Core Rulebook's own names, which are never wrong —
    a world that says nothing about money gets copper, silver, gold and platinum
    pieces, and the game works.
    """
    stated = _stated_currency(world, place)
    if stated:
        head = stated.split()[0]
        return [Coin(cid, f"{head} {METALS[cid]} piece", value)
                for cid, value in DENOMINATIONS]

    marker = _proper_noun(world, place) if world is not None else ""
    if marker:
        # "…piece" on the end of both branches, so the plural is "pieces". Naming the
        # coin after the metal alone gave "2 Khy'vyr golds".
        return [Coin(cid, f"{marker} {METALS[cid]} piece", value, coined=True)
                for cid, value in DENOMINATIONS]
    return [Coin(cid, f"{METALS[cid]} piece", value) for cid, value in DENOMINATIONS]


# The words a denomination's name can end on, with any plural `s` taken off: the ids,
# the metals, and the "piece"/"coin" every coined name ends with (`coinage`).
_MONEY_LAST = frozenset({"cp", "sp", "gp", "pp", "copper", "silver", "gold", "platinum",
                         "piece", "coin"})


def coin_named(text: str, coins: list[Coin] | None = None) -> str:
    """The denomination id a piece of text is asking for, or "".

    Reads both the id and the metal, in this world's names and in the book's, because
    the GM writes "three silver" as readily as "3 sp" and a player writes either.
    """
    want = str(text or "").strip().lower().rstrip("s")
    # The last word has to be money. "gold ring" starts with "gold", and read on the
    # metal alone it was a gold piece: a ring picked up went into the purse. The same
    # family as item 3 of 2026-10-03, where "the coins" went into the goods.
    last = (re.findall(r"[a-z]+", want.replace("_", " ")) or [""])[-1].rstrip("s")
    if last not in _MONEY_LAST:
        return ""
    for cid, _ in DENOMINATIONS:
        if want == cid or want.startswith(METALS[cid]):
            return cid
    for coin in coins or []:
        if want == coin.id or want in coin.name.lower():
            return coin.id
    for cid in METALS:
        if re.search(rf"\b{METALS[cid]}\b", want):
            return cid
    return ""


def in_copper(purse: dict) -> int:
    return sum(int(n) * dict(DENOMINATIONS).get(cid, 0) for cid, n in (purse or {}).items())


def spend(purse: dict, cost_cp: int) -> tuple[dict, bool]:
    """Pay a price, making change upward when the small coins run out.

    Returns the purse unchanged and False when there is genuinely not enough, so a
    refusal is a fact about the money rather than a negative balance nobody noticed.
    """
    cost_cp = max(0, int(cost_cp))
    if in_copper(purse) < cost_cp:
        return dict(purse or {}), False
    left = {cid: int(n) for cid, n in (purse or {}).items() if int(n) > 0}
    owed = cost_cp
    for cid, value in DENOMINATIONS:                       # smallest coins first
        while owed >= value and left.get(cid, 0) > 0:
            left[cid] -= 1
            owed -= value
    if owed:
        # Break the smallest coin big enough, and take the change back down.
        for cid, value in DENOMINATIONS:
            if value > owed and left.get(cid, 0) > 0:
                left[cid] -= 1
                return _add_change(left, value - owed), True
    return {c: n for c, n in left.items() if n > 0}, True


def credit(purse: dict, amount_cp: int) -> dict:
    """Money into a purse, counted up into the largest coins it makes.

    The counterpart to `spend`. There was no public one until treasure started coming
    off the fallen, because until then nothing in the game ever paid the player.

    The *whole* purse is recounted, not just the coin arriving. `_add_change` only ever
    carried the new amount, so what was already there kept its shape and the piles grew
    sideways: measured in play after two sales, Thessaly's purse read

        {'gp': 9, 'sp': 18, 'cp': 12}

    which is eighteen silver pieces and twelve coppers — 1,092 copper written in a way
    no purse in the world has ever been counted. Nobody carries twelve coppers when ten
    of them are a silver.
    """
    total = in_copper(purse) + max(0, int(amount_cp))
    return _add_change({}, total)


def coins_for(amount_cp: int) -> dict:
    """A bare amount as the coins it would be counted out in, largest first.

    A price is not a purse, but it is written the same way, and `purse_line` is the one
    place that knows how this world spells its money.
    """
    return _add_change({}, max(0, int(amount_cp)))


def _add_change(purse: dict, amount_cp: int) -> dict:
    out = {c: n for c, n in purse.items() if n > 0}
    for cid, value in reversed(DENOMINATIONS):
        if amount_cp >= value:
            out[cid] = out.get(cid, 0) + amount_cp // value
            amount_cp %= value
    return {c: n for c, n in out.items() if n > 0}


def purse_line(purse: dict, coins: list[Coin] | None = None) -> str:
    """What is in the purse, largest first, in this world's words."""
    names = {c.id: c for c in (coins or coinage())}
    parts = [f"{n} {names[cid].name if n == 1 else names[cid].plural}"
             for cid, _ in reversed(DENOMINATIONS)
             for n in [int((purse or {}).get(cid, 0))] if n]
    return ", ".join(parts) or "nothing"


def known_item(name: str) -> dict | None:
    """The Core-table entry for this thing, if the tables have one, with `table` saying
    which (weapon, ammunition, armour or shield) and `key` its one key.

    Read through the two resolvers (`armour.key_for`, `weapons.key_for`) since 2026-09-30.
    This used to look only in the curated twelve-row `tables.WEAPONS`, so of the 356
    weapons the smith sold, 348 were "gear" here — and `wear`, the Equipment tab and the
    shelves all asked this. Armour first: "light shield" is a shield to wear before it is
    the shield-bash row of the same name. A thing the general store sells under exactly
    this name is that gear, not a weapon that shares a word with it (the import has a
    "Grappling hook" weapon and a siege "Alchemist's fire"; the store sells both as gear).
    """
    from . import armour as armour_mod
    from . import weapons as weapons_mod

    low = " ".join(str(name or "").split()).lower()
    if not low or low in GEAR or low in _GEAR_NAMES:
        return None
    kind, key = armour_mod.key_for(low)
    if kind:
        return dict(ARMOUR[key] if kind == "armour" else SHIELDS[key], table=kind, key=key)
    key = weapons_mod.key_for(low)
    if key:
        row = weapons_mod.all_weapons()[key]
        kind = "ammunition" if weapons_mod.is_ammunition(key) else (
            "gear" if row.get("not_ammo") else "weapon")
        return dict(row, table=kind, key=key)
    return None


def canonical(name: str) -> str:
    """The one key a weapon, a round, a suit or a shield is stored under, else the name
    itself, lowered. What `wear`, `deliver` and the loot write, so a save never again holds
    "chain-shirt" where the table says "chain shirt"."""
    found = known_item(name)
    return str(found["key"]) if found else " ".join(str(name or "").split()).lower()


# Things you drink, eat or smear on a blade. Matched on the head noun, because the
# fiction names them "a potion of cure light wounds" and "willow-bark tea", and the
# crafting bench already knows what to do with anything that reaches `stock`.
_CONSUMABLE = re.compile(
    r"\b(?:potion|tincture|tea|draught|draft|elixir|philtre|philter|tonic|salve|"
    r"poultice|oil|unguent|balm|brew|infusion|decoction|antitoxin|antidote|ration|"
    r"rations|poison|venom)\b", re.I)

# Things measured out rather than counted: rope, chain, cloth, cord. The count is the
# quantity and the unit travels with it, so fifty feet of rope is one entry and not
# fifty ropes.
MEASURED = {"rope": "ft", "chain": "ft", "cord": "ft", "twine": "ft", "silk": "ft",
            "cloth": "ft", "wire": "ft", "fuse": "ft", "candle": "hours"}


def kind_of(name: str) -> str:
    """Which shelf this thing belongs on: weapon, ammunition, armour, shield, consumable
    or gear.

    Routing by what a thing *is* rather than dropping everything in one bag is the
    difference between an inventory and a list of nouns. A bought longsword should be
    swingable, a bought chain shirt wearable, and a bought potion drinkable through the
    machinery that already exists for all three. Ammunition is its own shelf since
    2026-09-30: a quiver of arrows is spent by the bow, never held (E3).
    """
    entry = known_item(name)
    if entry:
        return entry["table"]
    return "consumable" if _CONSUMABLE.search(str(name or "")) else "gear"


def stow(actor, name: str, count: int = 1) -> tuple[str, int]:
    """Put `count` of a thing where the sheet reads it, by what it is: (key, how many).

    The one router for a weapon, a round, a suit and a shield, so `deliver`, the loot
    and a handover cannot file one thing three ways. A weapon goes on the weapons list
    (that is what the attack op and `wear` read); ammunition goes into `goods` as single
    rounds — "Arrows (20)" bought three times is 60 arrows, which is what a shot spends
    one of (E3); armour and a shield into `goods` by their table key, to be put on with
    `wear`. Anything else is not this function's: the callers keep their own paths for
    gear, jars and herbs. ("", 0) when it is none of the four."""
    from . import weapons as weapons_mod

    entry = known_item(name)
    count = max(0, int(count or 0))
    if not entry or entry["table"] not in ("weapon", "ammunition", "armour", "shield"):
        return "", 0
    key = str(entry["key"])
    if entry["table"] == "weapon":
        for _ in range(count):
            actor.weapons.append(key)
        return key, count
    if entry["table"] == "ammunition":
        # A bundle's name says how many it is; a single key ("arrows-20") named once is
        # the bundle, so twenty. A count already in rounds is the caller's to pass as
        # `count` with a name that has no bundle in it.
        n = count * weapons_mod.rounds_per(key)
        actor.goods[key] = int(actor.goods.get(key, 0) or 0) + n
        return key, n
    actor.goods[key] = int(actor.goods.get(key, 0) or 0) + count
    return key, count


def ammo_carried(actor, families) -> list[dict]:
    """The rounds this actor carries of any of these families, most plentiful first:
    [{"key": "arrows-20", "name": "arrows", "count": 58, "family": "arrows"}]. Rounds
    live in `goods` under the bundle's key, counted singly (`stow`)."""
    from . import weapons as weapons_mod

    want = {str(f) for f in families or ()}
    out = []
    for name, n in (getattr(actor, "goods", None) or {}).items():
        if int(n or 0) <= 0 or not weapons_mod.is_ammunition(name):
            continue
        fam = weapons_mod.family_of(name)
        if fam in want:
            key = weapons_mod.key_for(name)
            out.append({"key": key, "stored": name, "family": fam, "count": int(n),
                        "name": weapons_mod.round_name(key, int(n))})
    out.sort(key=lambda r: (-r["count"], r["key"]))
    return out


def spend_round(actor, families, prefer: str = "") -> dict | None:
    """Take one round of these families out of `goods` for a shot: the one asked for if
    it is carried, else the most plentiful. Returns {"key", "family", "left"} — left is
    every round of the families still carried — or None when there is none to spend."""
    have = ammo_carried(actor, families)
    if not have:
        return None
    from . import weapons as weapons_mod

    want = weapons_mod.key_for(prefer) if prefer else ""
    pick = next((r for r in have if r["key"] == want), have[0])
    stored = pick["stored"]
    actor.goods[stored] = int(actor.goods[stored]) - 1
    if actor.goods[stored] <= 0:
        del actor.goods[stored]
    left = sum(r["count"] for r in have) - 1
    return {"key": pick["key"], "family": pick["family"], "left": left}


def unit_for(name: str) -> str:
    """"ft" for rope, "" for a lantern."""
    words = re.findall(r"[a-z]+", str(name or "").lower())
    for word in words:
        if word in MEASURED:
            return MEASURED[word]
    return ""


def describe(name: str, count: int = 1) -> str:
    """One line for the inventory list, and honest about what the engine knows.

    An item the tables do not carry is still carried by the character. Saying so
    plainly is the difference between "the engine has no rules for this" and the
    player assuming their lucite crystal does something.
    """
    from . import gear as gear_mod

    entry = known_item(name)
    unit = unit_for(name)
    # Measured goods read as a quantity, not a tally: fifty feet of rope, never
    # "50 × rope", which is what the count alone said.
    head = (f"{name} — {measure(count, unit)}" if unit
            else f"{count} × {name}" if count != 1 else str(name))
    # What a bedroll or a tent does is content/rules/gear.json's (2026-10-01): said in
    # its words, not "no rules for it", the line the owner read as "no effect".
    said = gear_mod.does(name)
    if said and (entry is None or entry.get("table") == "gear"):
        return f"{head} — {said}"
    if entry is None:
        return (head if unit else f"{head} — carried; "
                f"the engine has no rules for it")
    if entry.get("table") == "weapon":
        return f"{head} — {entry['damage']} {entry['type']}, ×{entry['crit_mult']}"
    if entry.get("table") == "ammunition":
        from . import weapons as weapons_mod

        word = weapons_mod.round_name(entry["key"], count)
        return f"{count} {word} — ammunition, spent one a shot"
    if entry.get("table") == "gear":
        return f"{head} — carried; the engine has no rules for it"
    return f"{head} — +{entry.get('ac', 0)} AC"


# --- adventuring gear, at the Core Rulebook's prices --------------------------------------------
# What the outfitting screen sells beside the weapon and armour tables: "at the end of
# making your character we need a buy screen to spend starting gold" (2026-09-07).
# Prices are the Core Rulebook's own, in gold; a thing measured rather than counted
# says its unit. Bought gear lands in `stock` like anything else the engine sells.
# `lb` is the Core Rulebook's weight for one purchase (`per` of the unit), added
# 2026-10-01 so carrying capacity has something to count (`rules/gear.py:load`); what a
# carried thing DOES is content/rules/gear.json's, never this table's.
GEAR: dict[str, dict] = {
    "backpack": {"name": "backpack", "cost_gp": 2.0, "lb": 2},
    "bedroll": {"name": "bedroll", "cost_gp": 0.1, "lb": 5},
    "blanket": {"name": "blanket", "cost_gp": 0.5, "lb": 3},
    "rope": {"name": "hemp rope", "cost_gp": 1.0, "unit": "ft", "per": 50, "lb": 10},
    "silk rope": {"name": "silk rope", "cost_gp": 10.0, "unit": "ft", "per": 50, "lb": 5},
    "torch": {"name": "torch", "cost_gp": 0.01, "lb": 1},
    "lantern": {"name": "hooded lantern", "cost_gp": 7.0, "lb": 2},
    "oil": {"name": "flask of oil", "cost_gp": 0.1, "lb": 1},
    "rations": {"name": "trail rations", "cost_gp": 0.5, "unit": "days", "per": 1, "lb": 1},
    "waterskin": {"name": "waterskin", "cost_gp": 1.0, "lb": 4},
    "flint and steel": {"name": "flint and steel", "cost_gp": 1.0, "lb": 0},
    "healer's kit": {"name": "healer's kit", "cost_gp": 50.0, "lb": 1},
    "grappling hook": {"name": "grappling hook", "cost_gp": 1.0, "lb": 4},
    "crowbar": {"name": "crowbar", "cost_gp": 2.0, "lb": 5},
    "chalk": {"name": "chalk", "cost_gp": 0.01, "lb": 0},
    "sack": {"name": "sack", "cost_gp": 0.1, "lb": 0.5},
    "whetstone": {"name": "whetstone", "cost_gp": 0.02, "lb": 1},
    "tent": {"name": "tent", "cost_gp": 10.0, "lb": 20},
    "antitoxin": {"name": "antitoxin", "cost_gp": 50.0, "lb": 0},
    "shovel": {"name": "shovel", "cost_gp": 2.0, "lb": 8},
    "hammer": {"name": "hammer", "cost_gp": 0.5, "lb": 2},
    "pitons": {"name": "pitons", "cost_gp": 0.1, "lb": 0.5},
    "mirror": {"name": "small steel mirror", "cost_gp": 10.0, "lb": 0.5},
    "thieves' tools": {"name": "thieves' tools", "cost_gp": 30.0, "lb": 1},
    "spell component pouch": {"name": "spell component pouch", "cost_gp": 5.0, "lb": 2},
    "holy symbol": {"name": "wooden holy symbol", "cost_gp": 1.0, "lb": 0},
    "manacles": {"name": "manacles", "cost_gp": 15.0, "lb": 2},
    "candle": {"name": "candle", "cost_gp": 0.01, "unit": "hours", "per": 1, "lb": 0},
    "ink and paper": {"name": "ink and paper", "cost_gp": 8.4, "lb": 0},
    "signal whistle": {"name": "signal whistle", "cost_gp": 0.8, "lb": 0},
    "fishing net": {"name": "fishing net", "cost_gp": 4.0, "lb": 5},
    "cold-weather outfit": {"name": "cold-weather outfit", "cost_gp": 8.0, "lb": 7},
    "traveler's outfit": {"name": "traveler's outfit", "cost_gp": 1.0, "lb": 5},
    "climber's kit": {"name": "climber's kit", "cost_gp": 80.0, "lb": 5},
    "caltrops": {"name": "caltrops", "cost_gp": 1.0, "lb": 2},
    "sunrod": {"name": "sunrod", "cost_gp": 2.0, "lb": 1},
    "alchemist's fire": {"name": "alchemist's fire", "cost_gp": 20.0, "lb": 1},
    # The rest of the CRB's alchemical eight (Goods and Services, "Special Substances and
    # Items", legacy.aonprd.com/coreRulebook/equipment.html, read 2026-10-06), added for
    # the alchemy plan §12.5. What every one of the eight DOES is its formula's book core
    # (`CLASSIC_GEAR` below), never a row here.
    "acid": {"name": "acid", "cost_gp": 10.0, "lb": 1},
    "tanglefoot bag": {"name": "tanglefoot bag", "cost_gp": 50.0, "lb": 4},
    "smokestick": {"name": "smokestick", "cost_gp": 20.0, "lb": 0.5},
    "tindertwig": {"name": "tindertwig", "cost_gp": 1.0, "lb": 0},
    "thunderstone": {"name": "thunderstone", "cost_gp": 30.0, "lb": 1},
    # The blacksmith's field kit (docs/blacksmithing-revamp-plan.md §10; `places.FIELD_KIT`
    # names it): common and uncommon smithing anywhere, without a smithy. PROPOSED price
    # and weight, not the book's, which prints no such kit: Ultimate Equipment's farrier's
    # anvil (50 lb) plus artisan's tools (5 gp, 5 lb) and a whetstone, rounded to 15 gp
    # and 55 lb. The owner may tune both; what carrying it does is content/rules/gear.json.
    "smith's field kit": {"name": "smith's field kit", "cost_gp": 15.0, "lb": 55},
    # The alchemist's field kit (docs/alchemy-revamp-plan.md §14; `places.ALCHEMY_KIT`
    # names it): Dissolve, Calcine, Filter, React, Bottle and Assay on common and uncommon
    # reagents anywhere. The BOOK's price and weight: Ultimate Equipment p.77's alchemy
    # crafting kit, 25 gp and 5 lb (aonprd, read 2026-10-07). Before this row the bench
    # asked for a kit nobody sold, so lane G's real `has_alchemy_kit` refused every step
    # of a new alchemist with "Needs a field kit or a laboratory" and no counter could
    # end the refusal.
    "alchemist's field kit": {"name": "alchemist's field kit", "cost_gp": 25.0, "lb": 5},
    # The plan §8.4's protection from a reagent that is toxic to handle, the fume hood's
    # carried half. PROPOSED 5 gp (the plan's number) and 1 lb: no book prints it.
    "alchemist's mask and gloves": {"name": "alchemist's mask and gloves", "cost_gp": 5.0,
                                    "lb": 1},
    # Food and drink, Core Rulebook Table 6-9 ("Food, Drink, and Lodging"), read from the
    # PRD's own table 2026-09-27 (legacy.aonprd.com/coreRulebook/equipment.html). Open
    # Game Content; the book is in OGL-NOTICE.md's section 15. Provisions a market sells
    # too; drink and meals are a tavern's. Lodging and banquets are services, not goods.
    "bread": {"name": "loaf of bread", "cost_gp": 0.02, "category": "provisions", "lb": 0.5},
    "cheese": {"name": "hunk of cheese", "cost_gp": 0.1, "category": "provisions", "lb": 0.5},
    "meat": {"name": "chunk of meat", "cost_gp": 0.3, "category": "provisions", "lb": 0.5},
    "ale": {"name": "mug of ale", "cost_gp": 0.04, "category": "food"},
    "ale gallon": {"name": "gallon of ale", "cost_gp": 0.2, "category": "food"},
    "wine": {"name": "pitcher of common wine", "cost_gp": 0.2, "category": "food"},
    "fine wine": {"name": "bottle of fine wine", "cost_gp": 10.0, "category": "food"},
    "good meal": {"name": "good meal", "cost_gp": 0.5, "category": "food"},
    "common meal": {"name": "common meal", "cost_gp": 0.3, "category": "food"},
    "poor meal": {"name": "poor meal", "cost_gp": 0.1, "category": "food"},
}
# The general store's own names, which `known_item` hands back as gear before it asks the
# weapon table: "grappling hook" and "alchemist's fire" are rows there too.
_GEAR_NAMES = frozenset(str(v["name"]).lower() for v in GEAR.values())


# --- goods on a counter ---------------------------------------------------------------------
#
# A shop's shelf was drawn only from the crafting benches' materials, so a market stall
# sold alum, bismuth and quicklime and no rope, no torch and no bread. Measured live
# 2026-09-27: "I try to buy a coil of rope." — the narrator invented a rope seller and
# handed rope over at one in the morning with no coin moving, and even had the purchase
# reached the engine there was no rope on any shelf to buy. The goods are the Core
# Rulebook's (`GEAR` above, the same list the outfitting screen sells from), and a counter
# stocks the ones its trade would: staples, always there, never sold out — a general
# store does not run out of rope by noon.
_SMITH_GOODS = frozenset({"crowbar", "grappling hook", "hammer", "pitons", "manacles",
                          "shovel", "caltrops", "whetstone", "lantern", "mirror",
                          "smith's field kit"})
def _category(key: str) -> str:
    return str((GEAR.get(key) or {}).get("category") or "gear")


def stocked_at(counter_kind: str) -> list[str]:
    """The GEAR keys a counter of this kind always has on it.

    A tavern or inn sells food and drink; a smithy, what a smith makes; a counter at the
    market (`market:<counter>`) or the stables, what `content/rules/stall-lines.json`
    gives it; everything else that keeps a counter sells the general goods, which is
    what the market as a whole ("market") has always sold."""
    kind = str(counter_kind or "").lower().removeprefix("the ")
    if kind in ("tavern", "inn", "alehouse", "taproom"):
        return [k for k in GEAR if _category(k) in ("food", "provisions")] + ["rations"]
    if kind in ("smithy", "workshops"):
        return [k for k in GEAR if k in _SMITH_GOODS]
    if kind == "laboratory":
        # The laboratory's keeper is the alchemist (places.STAFFED), and sells what the
        # market's alchemist sells over the counter: the book's alchemical goods, the
        # field kit, the mask and gloves. One list, the alchemist shop's own row in
        # stall-lines.json, so the two counters cannot drift. Before this the laboratory
        # fell to the "everything else" branch and sold rope, tents and a crowbar.
        from . import market

        return list(market.gear_of("market:alchemist"))
    if kind.startswith("market:") or kind == "stables":
        from . import market

        return list(market.gear_of(kind))
    return [k for k in GEAR if _category(k) != "food"]


@dataclass(frozen=True)
class Good:
    """One of the Core Rulebook's goods on a shelf, in the shape the counter reads:
    `id`, `name`, `tier`, `price_gp`. `per` is how much one purchase is — fifty feet of
    rope — and `unit` what it is measured in.

    `kind` is which part of the sheet a purchase lands on (`deliver`): gear and tack in
    the pack, a weapon in the weapon list, armour and shields carried to be worn, and a
    mount into the scene as a creature (`template`, a bestiary block). `key` is the
    catalogue's own key for it — the weapon table's `longsword`, the armour table's
    `chain shirt` — which is what the sheet stores."""
    id: str
    name: str
    price_gp: float
    tier: str = "common"
    per: int = 1
    unit: str = ""
    specs: tuple = ()
    staple: bool = True
    kind: str = "gear"
    key: str = ""
    template: str = ""

    @property
    def label(self) -> str:
        # "animal feed (1 day)", not "(1 days)": the unit is written plural in the tables
        # ("days", "hours") and one of it is singular. Seen on the trade window
        # (docs/fix-interfaces.md, I7). "ft" is its own singular.
        return f"{self.name} ({measure(self.per, self.unit)})" if self.unit else self.name


def measure(n: int, unit: str) -> str:
    """"1 day", "2 days", "50 ft": a count in its unit, singular for one. The tables write
    the unit plural, and the trade window showed "animal feed (1 days)" (I7); the buy tell
    reads this too, so the two cannot disagree."""
    return f"{n} {unit.removesuffix('s') if n == 1 else unit}"


GOOD_PREFIX = "gear:"
# What each kind of good is filed under on a shelf. The id carries the kind, so a row
# picked on the screen names its own shelf with nothing looked up twice.
PREFIXES = {"gear": "gear:", "weapon": "weapon:", "armour": "armour:", "shield": "shield:",
            "mount": "mount:", "tack": "tack:", "manual": "manual:", "alchemy": "alchemy:"}
# The smallest coin, for the four weapons the Core Rulebook prints a dash for (club,
# quarterstaff, sling, wooden stake). The outfit page gives them away; a counter cannot,
# because `pricing.worth` reads an authored price of 0 as "no price written" and prices
# the thing by its tier instead — 3.75 sp for a club. A copper is the nearest a counter
# comes to free, and it is said here rather than hidden in the number.
FREE_AT_A_COUNTER_GP = 0.01


def good(key: str) -> Good | None:
    entry = GEAR.get(key)
    if not entry:
        return None
    return Good(id=GOOD_PREFIX + key, name=str(entry["name"]),
                price_gp=float(entry["cost_gp"]), per=int(entry.get("per", 1) or 1),
                unit=str(entry.get("unit", "") or ""), key=key)


def goods_at(counter_kind: str) -> list[Good]:
    kind = str(counter_kind or "").lower().removeprefix("the ")
    if kind.startswith("market:") or kind == "stables":
        from . import market

        return list(market.staples_of(kind))
    from . import market

    # A place's keeper carries its trade's consumables as well as its gear: the smithy
    # its fuel, flux and quench (content/rules/stall-lines.json `consumables.places`).
    return ([g for g in (good(k) for k in stocked_at(counter_kind)) if g is not None]
            + market.consumable_goods(market.consumables_at(kind)))


# --- the rest of the outfit page's catalogue, as goods ------------------------------------------
#
# "outfit page should not be reachable but there should be stores that carry all of those
# items in town split between a general goods store and armorer and a weaponsmith. add an
# alchemist and have the rest split up between random market stalls" (the owner,
# 2026-09-28). The outfit page sells the weapon, armour and shield tables and GEAR; GEAR
# was already goods, and these are the other three, in the same shape and at the same
# printed prices.

def outfit_weapons() -> dict[str, dict]:
    """The weapons the outfit page sells, by key: every weapon with a printed price,
    less the exotic ones over 100 gp.

    The same rule as `play/outfit_views.catalogue`, written twice because a rules module
    may not import a view; `tests/test_i2_market.py` holds the two copies to one answer,
    which is CLAUDE.md's "when you fix a rule, grep for every copy of it" made a test."""
    from . import weapons as weapons_mod

    out = {}
    for key, w in weapons_mod.all_weapons().items():
        cost = w.get("cost_gp")
        if cost in (None, "") or w.get("prof") == "exotic" and float(cost) > 100:
            continue
        # Owner's ruling E5 (2026-09-30): no siege engines and nothing "(Modern)" on a
        # weaponsmith's shelf. The rule is `weapons.UNSOLD_SECTION`, the one copy.
        if weapons_mod.UNSOLD_SECTION.search(str(w.get("section") or "")):
            continue
        out[key] = w
    return out


def weapon_good(key: str, w: dict | None = None) -> Good | None:
    """A row of the weapon table as a good, on the weaponsmith's shelf. What the row IS — a
    weapon, a bundle of ammunition, a shield (the shield-bash rows resolve to the shield
    to wear), a firearm's kit — is `deliver`'s to read off the key through `stow`, so the
    shelf stays the smith's and the purchase still lands where it can be used."""
    w = w if w is not None else outfit_weapons().get(key)
    if not w:
        return None
    return Good(id=PREFIXES["weapon"] + key, name=str(w.get("name", key)),
                price_gp=float(w["cost_gp"]) or FREE_AT_A_COUNTER_GP,
                kind="weapon", key=key)


def armour_good(key: str) -> Good | None:
    a = ARMOUR.get(key)
    if not a or not a.get("cost_gp"):
        return None
    return Good(id=PREFIXES["armour"] + key, name=str(a["name"]),
                price_gp=float(a["cost_gp"]), kind="armour", key=key)


def shield_good(key: str) -> Good | None:
    s = SHIELDS.get(key)
    if not s or not s.get("cost_gp"):
        return None
    return Good(id=PREFIXES["shield"] + key, name=str(s["name"]),
                price_gp=float(s["cost_gp"]), kind="shield", key=key)


def table_goods(table: str) -> list[Good]:
    """Every row of one Core table the outfit page sells, as goods."""
    if table == "weapons":
        return [weapon_good(k, w) for k, w in outfit_weapons().items()]
    if table == "armour":
        return [g for g in (armour_good(k) for k in ARMOUR) if g is not None]
    if table == "shields":
        return [g for g in (shield_good(k) for k in SHIELDS) if g is not None]
    if table in MANUAL_TABLES:
        # The crafts' manuals — herbal (docs/herbalism-revamp-plan.md §8.4), smithing
        # (docs/blacksmithing-revamp-plan.md §9.3) and enchanting (docs/enchanting-revamp-
        # plan.md §12.3) — carried like any book: `deliver` shelves one under its name,
        # which is what `knowledge.holds_manual` looks for when the reader opens it. One
        # builder for the three: they were two copies of one comprehension before the
        # enchanting books would have made it three.
        from . import knowledge

        return [Good(id=PREFIXES["manual"] + m["id"], name=str(m["name"]),
                     price_gp=float(m["price_gp"]), kind="gear", key=str(m["id"]))
                for m in knowledge.manuals(MANUAL_TABLES[table]).values()]
    if table == ALCHEMY_CLASSICS:
        return alchemy_classic_goods()
    return []


# Which craft's manuals each counter table sells (content/rules/stall-lines.json `tables`).
# The alchemy manuals were the 0.2.4 defect waiting to happen again: a craft's books on no
# counter. The alchemist's shop names this table (stall-lines.json), and a test holds every
# manual of every craft to some counter.
MANUAL_TABLES = {"herbal-manuals": "herbalist", "smithing-manuals": "blacksmith",
                 "enchanting-manuals": "enchanter", "alchemy-manuals": "alchemist"}


# --- the alchemist's goods are the bench's own products (alchemy plan §12.5, owner Q8.3) -----
#
# Before this, a bought alchemist's fire, antitoxin or sunrod was a jar with a name and no
# document (`deliver` made `Stock(base=name)` and nothing else): the antitoxin a counter sold
# "the GM narrates" (rules/consumables.py), and the flask could not be thrown at anybody.
# The owner's Q8.3: "the same documents as the crafted ones", bought at Sound quality. So a
# bought classic is built from its FORMULA ROW (content/rules/alchemy-formulae.json, lane E)
# — the book core, the book price — and so is a potion on sale. One item, whether bought or
# made; nothing here restates what an item does.
#
# The CRB eight keep their GEAR rows (the outfit page sells from GEAR, and the alchemist's
# shop names them), and this map is the one place a GEAR key becomes its formula. The other
# ten classics (Ultimate Equipment's, and the house holy weapon balm) have no GEAR row and
# are sold as the `alchemy-classics` table. tests/test_alchemy_prices.py holds every GEAR
# price here to its formula's printed price, so the two cannot drift.
CLASSIC_GEAR: dict[str, str] = {
    "alchemist's fire": "alchemists-fire", "acid": "acid-flask", "antitoxin": "antitoxin",
    "sunrod": "sunrod", "tanglefoot bag": "tanglefoot-bag", "smokestick": "smokestick",
    "tindertwig": "tindertwig", "thunderstone": "thunderstone",
}
ALCHEMY_CLASSICS = "alchemy-classics"
# How each family is used (alchemy plan §12.1, "Used by"): drunk, coated or rubbed on,
# thrown, thrown at a square, struck or lit. What `consumables.plan` reads in `Stock.how`.
FAMILY_HOW: dict[str, tuple[str, ...]] = {
    "potion": ("drink",), "oil": ("coat", "apply"), "splash": ("throw",),
    "cloud": ("throw",), "tool": ("light",),
}


def alchemy_stock(fid: str):
    """The stock row a bought formula product is: the formula's own core at Sound quality
    (its book numbers), its family's uses, and — for a potion holding a spell — the spell
    and its caster level, so the enchanter's stand-in and the drink door both read it
    (contracts §6: `holds_spell` and `caster_level` always written). A derived spell row has
    no authored core: its `specs` stay empty and the drink resolves the spell's own documents
    (`consumables.spell_of`). None for an id that is no formula."""
    from . import effectspec, formulae
    from .crafting import Stock

    row = formulae.get(fid)
    if row is None:
        return None
    specs = [dict(s) for s in (row.get("core") or ())]
    family = str(row.get("family") or "")
    return Stock(base=str(row["name"]), tier=str(row.get("tier") or "common"), potency=1.0,
                 craft="alchemist", specs=specs,
                 effects=[effectspec.render(s) for s in specs],
                 how=list(FAMILY_HOW.get(family, ())), quality=formulae.SOUND,
                 holds_spell=row.get("spell") if row.get("kind") == "spell" else None,
                 caster_level=row.get("caster_level") if row.get("kind") == "spell" else None)


def _alchemy_good(row: dict, *, staple: bool) -> Good:
    from . import pricing

    return Good(id=PREFIXES["alchemy"] + str(row["id"]), name=str(row["name"]),
                price_gp=float(pricing.book_price(row) or 0), tier=str(row.get("tier") or "common"),
                staple=staple, kind="alchemy", key=str(row["id"]))


def alchemy_classic_goods() -> list[Good]:
    """Every brewable classic a GEAR row does not already sell, as a staple of the
    alchemist's counter at its book price."""
    from . import formulae

    geared = set(CLASSIC_GEAR.values())
    return [_alchemy_good(r, staple=True) for fid, r in sorted(formulae.all().items())
            if r.get("kind") == "classic" and r.get("brewable", True) and fid not in geared]


def potion_goods() -> list[Good]:
    """Every brewable spell potion and oil, at Sound quality and the book price (plan
    §12.5), for the alchemist's daily draw: NOT staples. Which of them a counter has today
    is the market's existing rule — the rarity quota and the till (`market.on_sale`) — so
    the alchemist's till bounds the dearest potion it shelves.

    A harmful spell's row is left off the counter: bought, it is a potion, and a potion's
    target is its drinker (owner, open point 5) — a shop selling "potion of touch of
    fatigue" to drink is selling poison as medicine. Its thrown-flask form is the bench's.

    Only the authored potions — the 44 classics (cure wounds, invisibility, fly…) — are
    sold. Owner, 2026-10-07: shops sell "the 44 classic potions"; with every derived row
    the counter offered 109 potions, oddities like "Rejuvenate Eidolon, Lesser" among
    them. Derived formulae are the bench's, from writings and experiment."""
    from . import formulae

    return [_alchemy_good(r, staple=False) for fid, r in sorted(formulae.all().items())
            if r.get("kind") == "spell" and r.get("authored") and r.get("brewable", True)
            and not r.get("harmful")]


def catalogue_ids() -> set[str]:
    """The id of every good the outfit page sells — what "every item is buyable in play"
    is measured against."""
    ids = {GOOD_PREFIX + k for k in GEAR}
    for table in ("weapons", "armour", "shields"):
        ids |= {g.id for g in table_goods(table)}
    return ids


def stables_goods() -> list[Good]:
    """The animals and the tack, at the prices `content/rules/stall-lines.json` carries
    (d20pfsrd "Animals & Animal Gear"). An animal is a `mount` good with the bestiary
    block it is made from; the tack is carried like any gear."""
    from . import market

    doc = market.lines_doc().get("stables") or {}
    out = []
    for row in doc.get("animals") or []:
        out.append(Good(id=PREFIXES["mount"] + str(row["key"]), name=str(row["name"]),
                        price_gp=float(row["cost_gp"]), kind="mount",
                        key=str(row["key"]), template=str(row.get("template") or "")))
    for row in doc.get("tack") or []:
        out.append(Good(id=PREFIXES["tack"] + str(row["key"]), name=str(row["name"]),
                        price_gp=float(row["cost_gp"]), kind="tack", key=str(row["key"]),
                        per=int(row.get("per", 1) or 1), unit=str(row.get("unit") or "")))
    return out


def deliver(scene, actor, found, count: int = 1) -> tuple[list[dict], str]:
    """Put what was just paid for where the sheet reads it: (effects, a sentence).

    Called by the engine's `buy` once the coin has moved, and nowhere else — a purchase
    is one op. Before this, everything bought became a pack entry, which is right for
    rope and wrong for a sword (the attack reads `weapons`), a hauberk (`wear` reads
    what is carried) and a horse, which is not a thing in a pack at all.

    **A mount comes into the scene as a creature**, through the arrival door
    (`Scene.add`), made from its bestiary block, and travels with the party: the
    `bond.travels-with-you` tag, through the one applicator, filed under `company:<ref>`
    so the `company` op's "leave" parts with it like anybody else who came along. That
    is exactly what `rules/journey.py` asks a mount to be — a creature in the party whose
    template is one of `journey.MOUNTS` — so the journey's ride and gallop paces apply to
    it with nothing in the journey changed. Bought, never hired (the owner, 2026-09-29);
    `origin` says so.
    """
    count = max(1, int(count or 1))
    kind = str(getattr(found, "kind", "") or "gear")
    key = str(getattr(found, "key", "") or getattr(found, "name", ""))
    if kind in ("weapon", "armour", "shield"):
        # Through the one router (`stow`): a weapon on the weapons list, a suit or a
        # shield carried to be put on with `wear`, and ammunition as single rounds —
        # "Arrows (20)" bought three times is 60 arrows, not three of a thing (E3).
        # What `stow` does not take (a firearm's kit off the smith's shelf) falls through
        # to the pack below, as gear.
        stowed, _ = stow(actor, key, count)
        if stowed:
            return [], ""
        if kind in ("armour", "shield"):
            actor.goods[key] = int(actor.goods.get(key, 0) or 0) + count
            return [], ""
    if kind == "mount" and getattr(found, "template", ""):
        from . import states
        from .activeeffect import ActiveEffect
        from .bestiary import instantiate

        effects, names = [], []
        for _ in range(count):
            # "light horse", not "light horse (combat-trained)": the training is what was
            # paid for, not what the animal is called.
            animal = instantiate(found.template, scene=scene,
                                 name=str(found.name).split(" (")[0])
            scene.add(animal)
            source = f"company:{animal.ref}"
            animal.apply_effect(ActiveEffect(
                name="travels with you", kind="bond", key=f"{source}:travels",
                source=source, origin=f"bought:{actor.ref}", duration="until-dismissed",
                tags=(states.TRAVELS_WITH_YOU,)))
            effects.append({"ref": animal.ref, "kind": "company", "travels": True,
                            "bought_by": actor.ref})
            names.append(animal.name)
        return effects, (f" The {names[0]} is {actor.name}'s now, and goes where they go."
                         if len(names) == 1 else
                         f" {', '.join(names)} are {actor.name}'s now, and go where "
                         f"they go.")
    per = int(getattr(found, "per", 1) or 1)
    # An alchemist's product — a classic off the shelf or a potion from today's draw — is
    # the bench's own stock row (`alchemy_stock`), so a bought antitoxin gives its +5 and a
    # bought flask of acid can be thrown (owner Q8.3).
    fid = (key if kind == "alchemy"
           else CLASSIC_GEAR.get(key) if isinstance(found, Good) and kind == "gear" else None)
    if fid:
        made = alchemy_stock(fid)
        if made is not None:
            actor.add_stock(made, count * per)
            return [], ""
    # A craft's material — a counter's staple charcoal, or one drawn onto today's shelf —
    # goes in the satchel under its own id, where every bench reads it and where the
    # forge's "Buy from the market" has always put it. Before this it became a pack jar
    # named "Charcoal" with no craft, which the forge's stock (filtered by craft) never
    # offered: bought fuel that could not be burned. Herbal reagents had a name-lookup
    # patch for the same hole (`crafting._reagent_for_stock`), kept for old saves.
    from . import market

    if kind == "material" or (not isinstance(found, Good) and market.is_craft_material(found)):
        mid = found.key if isinstance(found, Good) else str(getattr(found, "id", ""))
        actor.carry(mid, count * per)
        return [], ""
    from .crafting import Stock

    actor.add_stock(Stock(base=found.name, tier=str(getattr(found, "tier", "common")),
                          potency=1.0, craft=str(getattr(found, "track", "") or "")),
                    count * per)
    return [], ""


# The words a purchase is measured in and nothing else: "a coil of rope" is rope, "a loaf
# of bread" is bread, "some torches" is torches.
_MEASURE_WORDS = frozenset({
    "a", "an", "the", "some", "any", "of", "coil", "coils", "length", "lengths", "loaf",
    "loaves", "flask", "flasks", "mug", "mugs", "pitcher", "bottle", "bottles", "bag",
    "bags", "pair", "pairs", "set", "sets", "piece", "pieces", "few", "couple", "bit",
    "stick", "sticks", "roll", "rolls", "bundle", "one", "two", "three", "four", "five",
    "fifty", "feet", "foot", "ft", "day's", "days", "day", "worth", "new", "good",
    "decent", "cheap", "sturdy", "fresh", "hot", "cold", "more", "extra", "spare",
})


def _want_words(text: str) -> list[str]:
    from .population import _stem

    return [_stem(w) for w in re.findall(r"[a-z][a-z'-]*", str(text or "").lower())
            if w not in _MEASURE_WORDS]


def match_want(want: str, rows) -> tuple[object | None, list]:
    """The shelf row the player asked for, or None and what is nearest.

    Every word of the want must be in the row's name or id (after the measure words go):
    "a coil of rope" is hemp rope and silk rope both, and the cheaper, plainer one wins,
    as a shopkeeper asked for "rope" reaches for the ordinary coil. None fits: nothing
    is guessed (CircleMUD's keeper: "I don't have that") and the caller says so."""
    words = _want_words(want)
    if not words:
        # All measure: "a loaf" is the loaf of bread. The words themselves, then.
        from .population import _stem

        words = [_stem(w) for w in re.findall(r"[a-z][a-z'-]*", str(want or "").lower())
                 if w not in ("a", "an", "the", "some", "any", "of")]
    if not words:
        return None, []
    fits = []
    for r in rows:
        name = str(getattr(r, "name", "") or (r.get("name") if isinstance(r, dict) else ""))
        rid = str(getattr(r, "id", "") or (r.get("id") if isinstance(r, dict) else ""))
        from .population import _stem

        # The id's kind prefix ("gear:", "weapon:", "mount:") is filing, not a word the
        # player could have meant.
        bare = rid.split(":", 1)[1] if rid.split(":", 1)[0] + ":" in PREFIXES.values() \
            else rid
        have = {_stem(w) for w in re.findall(
            r"[a-z][a-z'-]*", f"{name} {bare.replace('-', ' ')}".lower())}
        if all(w in have for w in words):
            fits.append(r)
    if not fits:
        return None, []
    fits.sort(key=lambda r: fit_rank(want, r))
    return fits[0], fits


def _head(text: str) -> str:
    """The last word of a name, its parenthesis dropped: "light horse (combat-trained)" is
    a horse, "rope dart" a dart."""
    from .population import _stem

    words = re.findall(r"[a-z][a-z'-]*", re.sub(r"\([^)]*\)", "", str(text or "")).lower())
    return _stem(words[-1]) if words else ""


def fit_rank(want: str, row) -> tuple:
    """How well a shelf row answers the want, best first: the thing whose own head noun is
    the want's comes before a thing that merely has the word in it, and then the cheaper.

    Measured the day the weaponsmith's rack joined the market (I2): "a coil of rope" went
    to the weaponsmith, because the Core weapon table's "rope dart" costs less than the
    general store's hemp rope and cheapest-first was the whole ranking. A shopkeeper asked
    for rope reaches for rope, not for a weapon with rope in it."""
    words = _want_words(want)
    wanted = words[-1] if words else ""
    name = str(getattr(row, "name", "") or (row.get("name") if isinstance(row, dict) else ""))
    v = getattr(row, "price_gp", None)
    if v is None and isinstance(row, dict):
        v = row.get("gp")
    return (0 if wanted and _head(name) == wanted else 1, float(v or 0))
