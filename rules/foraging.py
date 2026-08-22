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
    span = 100 - MIN_NOTHING

    # A d100 table has room for `span` rows at one percent each, and a rich biome can
    # field more candidates than that. Which ones get cut has to be decided here rather
    # than left to wherever the cursor happened to run out. Laying the rows down
    # commonest-first and breaking when the table filled up deleted the *rarest* end —
    # the half the table exists to gate: forest fielded 105 candidates, kept 95, and lost
    # both of its exotic herbs and six of its seven rare ones while keeping all 88
    # commons. Trimming from the common end instead costs the player nothing they would
    # notice, because the commons that remain still fill four fifths of the table.
    if len(found) > span:
        found = found[len(found) - span:]

    weights = [WEIGHT.get(i.rank, 1) for i in found]
    total = sum(weights)

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


# --- an hour on the ground ----------------------------------------------------------------
#
# One Survival check an hour, and how far it beats the ground's difficulty decides
# everything: how much, how rare, and whether it comes back whole.
#
# The bands are the brief made numeric — "anything from a single destroyed leaf to a
# veritable garden's worth of perfectly picked glowing versions of every possible plant
# that could be picked". A botched hour is not merely an empty hour: it is a leaf torn off
# its stem and useless, which is worse than nothing because the plant is spent.

FORAGE_DC = {
    "farmland": 10, "grassland": 12, "forest": 12, "hills": 13, "coast": 14,
    "urban": 15, "jungle": 15, "swamp": 16, "ruins": 16, "mountain": 17,
    "underground": 18, "tundra": 19, "desert": 20, "planar": 20,
}
DEFAULT_FORAGE_DC = 15

# margin -> (label, how many finds, how much the rarity ceiling lifts, all pristine)
#
# The bottom band is not "nothing". It is a plant found and wrecked getting it out of the
# ground — the brief's "single destroyed leaf" — and it is named, because being told you
# tore the roots off a Woundwart is a different fact from being told the wood was bare.
# Nothing is carried either way; only one of them tells the player something.
BANDS = (
    (20, "a garden's worth", 8, 2, True),
    (15, "an excellent hour", 5, 1, True),
    (10, "a good hour", 3, 1, False),
    (5, "a fair hour", 2, 0, False),
    (0, "a meagre hour", 1, 0, False),
    (-5, "nothing worth carrying", 0, 0, False),
)
RUINED = ("a ruined handful", 0, 0, False)
RUINED_AT = -5


def dc_for(biome: str) -> int:
    return FORAGE_DC.get((biome or "").strip().lower(), DEFAULT_FORAGE_DC)


def band_for(margin: int) -> tuple:
    """(label, finds, ceiling lift, pristine) for how far the check beat the ground."""
    for floor, label, finds, lift, pristine in BANDS:
        if margin >= floor:
            return (label, finds, lift, pristine)
    return RUINED


def forage_hour(biome: str, level: int, rank_ceiling: int, dice, actor=None) -> dict:
    """One hour of looking, as one Survival check and what it turned up.

    The check is the character's own Survival, and the world class adds to it on top —
    an Herbalist knows where to look as well as what they are looking at. That bonus is
    the track's payoff on the ground, the way `attempts_for` is its payoff in yield.
    """
    from . import worldclass

    table = table_for(biome, rank_ceiling)
    dc = dc_for(biome)

    mods = []
    if actor is not None:
        mods = list(actor.skill_modifiers("survival"))
        level = int(level)
        if level > 0:
            from .dice import Modifier

            mods.append(Modifier(level, "herbalism"))
    roll = dice.d20(mods, label=f"Foraging ({table.biome})", visibility="player")
    margin = roll.total - dc
    label, finds, lift, pristine = band_for(margin)

    # A better hour also reaches rarer things, but never past what the track allows: the
    # ceiling is what the character can *handle*, and luck does not teach them.
    hour_ceiling = min(rank_ceiling, rank_ceiling + lift) if lift else rank_ceiling
    if lift:
        hour_ceiling = min(len(WEIGHT), rank_ceiling + lift)
        table = table_for(biome, hour_ceiling)

    found: dict[str, int] = {}
    picks = []
    for _ in range(finds):
        pick = dice.roll("1d100", label=f"Foraging ({table.biome})", visibility="hidden")
        row = table.lookup(pick.total)
        picks.append({"roll": pick.total, "found": row.name if row else None,
                      "id": row.ingredient_id if row else None})
        if row:
            found[row.ingredient_id] = found.get(row.ingredient_id, 0) + 1

    # A botched hour still names what was destroyed. Nothing is carried, but the player is
    # told they had a Woundwart in their hand and tore the roots off it.
    ruined = margin < RUINED_AT
    wrecked = ""
    if ruined and not table.empty:
        pick = dice.roll("1d100", label="what was spoiled", visibility="hidden")
        row = table.lookup(pick.total)
        wrecked = row.name if row else ""

    return {
        "biome": table.biome, "dc": dc, "roll": roll.total, "margin": margin,
        "band": label, "finds": finds, "ceiling": hour_ceiling,
        "pristine": bool(pristine and found), "ruined": ruined, "wrecked": wrecked,
        "picks": picks, "found": found, "empty": table.empty,
    }


def forage(biome: str, level: int, rank_ceiling: int, dice, hours: int = 1,
           actor=None) -> dict:
    """A foraging session of however many hours the player asked for.

    Hour by hour rather than one roll for the stretch. Each hour is its own check, so a
    long day is a spread of good and bad hours rather than a single verdict — and when
    something stops the character partway, the hours before it still happened.
    """
    hours = max(1, int(hours))
    found: dict[str, int] = {}
    pristine: dict[str, int] = {}
    each = []

    for _ in range(hours):
        hour = forage_hour(biome, level, rank_ceiling, dice, actor=actor)
        each.append(hour)
        for iid, n in hour["found"].items():
            found[iid] = found.get(iid, 0) + n
            if hour["pristine"]:
                pristine[iid] = pristine.get(iid, 0) + n

    return {
        "biome": each[0]["biome"] if each else biome,
        "hours": len(each), "attempts": sum(h["finds"] for h in each),
        "rolls": [p for h in each for p in h["picks"]],
        "hourly": each, "found": found, "pristine": pristine,
        "ruined_hours": sum(1 for h in each if h["ruined"]),
        # The best hour of the day, by how far its check beat the ground. What the player
        # wants told back to them after eighteen hours is the one that went well.
        "best": max(each, key=lambda h: h["margin"])["band"] if each else "",
        "empty": each[0]["empty"] if each else True,
    }
