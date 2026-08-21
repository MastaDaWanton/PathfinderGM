"""Forage tables, built from where you are.

A table is not authored per biome — it is assembled from the ingredient list every time,
by asking which forageable things grow here and how rare each one is. Thirteen biomes
times a hundred and sixty ingredients is two thousand hand-written rows nobody would keep
current; derived from the tags, a new herb appears on every table it belongs to the moment
it is added.

Rolled on a d100 because the spread of a forage table wants finer grain than a d20 —
a legendary find should be able to sit on a single percent.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import biomes as biome_mod
from . import ingredients as ing_mod

# How often each rarity turns up, before the biome narrows it. Roughly inverse to tier,
# steeply: finding a legendary herb should feel like an event, not a Tuesday.
WEIGHT = {1: 60, 2: 22, 3: 9, 4: 3, 5: 1}

# The slice of the table that is a wasted afternoon. Kept as a floor rather than a fixed
# share so a rich biome is genuinely better ground than a poor one, and a biome nothing is
# tagged for reads as empty instead of silently handing out whatever is nearest.
MIN_NOTHING = 5


@dataclass
class Row:
    low: int
    high: int
    ingredient_id: str
    name: str
    tier: str
    rank: int

    @property
    def span(self) -> int:
        return self.high - self.low + 1

    def as_dict(self) -> dict:
        return {"low": self.low, "high": self.high, "roll": f"{self.low}-{self.high}"
                if self.high > self.low else str(self.low),
                "id": self.ingredient_id, "name": self.name, "tier": self.tier,
                "rank": self.rank, "chance": self.span}


@dataclass
class Table:
    biome: str
    rank_ceiling: int
    rows: list[Row] = field(default_factory=list)
    nothing_from: int = 96

    @property
    def empty(self) -> bool:
        return not self.rows

    def lookup(self, roll: int) -> Row | None:
        for row in self.rows:
            if row.low <= roll <= row.high:
                return row
        return None

    def as_dict(self) -> dict:
        return {
            "biome": self.biome, "describe": biome_mod.describe(self.biome),
            "rank_ceiling": self.rank_ceiling,
            "rows": [r.as_dict() for r in self.rows],
            "nothing_from": self.nothing_from,
            "nothing_chance": max(0, 101 - self.nothing_from),
            "empty": self.empty,
        }


def table_for(biome: str, rank_ceiling: int = 5) -> Table:
    """Everything that grows here and can be worked at this tier, as a d100 table.

    The ceiling filters rather than merely marking, unlike the crafting shelf: you cannot
    recognise what you have no training to handle, and a table full of rows the character
    must throw away is worse than a shorter honest one.
    """
    biome = biome_mod.canonical(biome) or "grassland"
    found = [
        i for i in ing_mod.all_ingredients().values()
        if i.forageable and biome in i.biomes and i.rank <= rank_ceiling
    ]
    if not found:
        return Table(biome=biome, rank_ceiling=rank_ceiling, rows=[], nothing_from=1)

    found.sort(key=lambda i: (i.rank, i.name))
    weights = [WEIGHT.get(i.rank, 1) for i in found]
    total = sum(weights)
    span = 100 - MIN_NOTHING

    rows: list[Row] = []
    cursor = 1
    for ing, weight in zip(found, weights):
        # Every candidate gets at least one percent, so a rare herb in a thin biome is
        # findable rather than rounded out of existence.
        width = max(1, round(span * weight / total))
        if cursor > span:
            break
        high = min(span, cursor + width - 1)
        rows.append(Row(low=cursor, high=high, ingredient_id=ing.id, name=ing.name,
                        tier=ing.tier, rank=ing.rank))
        cursor = high + 1

    nothing_from = rows[-1].high + 1 if rows else 1
    return Table(biome=biome, rank_ceiling=rank_ceiling, rows=rows,
                 nothing_from=nothing_from)


def attempts_for(level: int) -> int:
    """How many things a forager turns up in one session.

    The track's visible payoff outside the workbench: an Herbalist 5 walking the same wood
    as an Herbalist 1 comes back with three times as much, without the tables changing at
    all.
    """
    return 1 + max(0, int(level)) // 2


def forage(biome: str, level: int, rank_ceiling: int, dice) -> dict:
    """One foraging session. Returns what was found and every roll that produced it."""
    table = table_for(biome, rank_ceiling)
    tries = attempts_for(level)
    found: dict[str, int] = {}
    rolls = []
    for _ in range(tries):
        roll = dice.roll("1d100", label=f"Foraging ({table.biome})", visibility="player")
        row = table.lookup(roll.total)
        rolls.append({"roll": roll.total, "found": row.name if row else None,
                      "id": row.ingredient_id if row else None})
        if row:
            found[row.ingredient_id] = found.get(row.ingredient_id, 0) + 1
    return {"biome": table.biome, "attempts": tries, "rolls": rolls, "found": found,
            "empty": table.empty}
