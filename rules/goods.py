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

from .tables import ARMOUR, SHIELDS, WEAPONS

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


def coin_named(text: str, coins: list[Coin] | None = None) -> str:
    """The denomination id a piece of text is asking for, or "".

    Reads both the id and the metal, in this world's names and in the book's, because
    the GM writes "three silver" as readily as "3 sp" and a player writes either.
    """
    want = str(text or "").strip().lower().rstrip("s")
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
    """The Core-table entry for this thing, if the tables have one."""
    key = " ".join(str(name or "").split()).lower()
    for table in (WEAPONS, ARMOUR, SHIELDS):
        if key in table:
            return dict(table[key], table=table is WEAPONS and "weapon"
                        or table is ARMOUR and "armour" or "shield")
    return None


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
    """Which shelf this thing belongs on: weapon, armour, shield, consumable or gear.

    Routing by what a thing *is* rather than dropping everything in one bag is the
    difference between an inventory and a list of nouns. A bought longsword should be
    swingable, a bought chain shirt wearable, and a bought potion drinkable through the
    machinery that already exists for all three.
    """
    entry = known_item(name)
    if entry:
        return entry["table"]
    return "consumable" if _CONSUMABLE.search(str(name or "")) else "gear"


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
    entry = known_item(name)
    unit = unit_for(name)
    # Measured goods read as a quantity, not a tally: fifty feet of rope, never
    # "50 × rope", which is what the count alone said.
    head = (f"{name} — {count} {unit}" if unit
            else f"{count} × {name}" if count != 1 else str(name))
    if entry is None:
        return (head if unit else f"{head} — carried; "
                f"the engine has no rules for it")
    if entry.get("table") == "weapon":
        return f"{head} — {entry['damage']} {entry['type']}, ×{entry['crit_mult']}"
    return f"{head} — +{entry.get('ac', 0)} AC"
