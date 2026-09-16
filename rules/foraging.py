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
    # Fishing, which is foraging with a line rather than with your hands. Harder from a
    # deck than from a shore only because you cannot wade out to the weed; harder again
    # below the surface, where what grows is holding on to rock.
    "water": 15, "deck": 16, "underwater": 17,
}
DEFAULT_FORAGE_DC = 15

# margin -> (label, how many finds, how much the rarity ceiling lifts, all pristine)
#
# The bottom band is not "nothing". It is a plant found and wrecked getting it out of the
# ground — the brief's "single destroyed leaf" — and it is named, because being told you
# tore the roots off a Woundwart is a different fact from being told the wood was bare.
# Nothing is carried either way; only one of them tells the player something.
#
# The top band is a floor, not a roof. "The base numbers of items foraged should continue
# going up as my roll gets higher" — so every OVER_STEP points of margin past the top
# floor is one more virtual band above it: more kinds found, bigger patches of each. The
# rarity ceiling does not keep lifting, because the ceiling is what the character can
# handle and luck does not teach them.
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
OVER_STEP = 5           # margin per virtual band above the top
OVER_FINDS = 2          # extra kinds per virtual band

# How many of a thing you get when you find it. The count in the bands above is how many
# *kinds* the hour turns up; this is how many of each.
#
# Plants grow in patches. Finding one flower of eight different species is not what a good
# hour in a wood looks like — you come out of it with an armful of the common stuff and,
# if you were lucky, a couple of the rare. So the batch falls with rarity, and falls again
# for every band the hour came in below the best:
#
#   common 10, uncommon 8, rare 6, exotic 4, legendary 2, minus two per band below the top
#
# Never below one: if the hour found it at all, the character is holding at least one of
# it. That floor is what keeps a legendary herb worth stooping for at every band rather
# than rounding away to nothing three bands down.
BATCH_TOP = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2}
BATCH_STEP = 2


def batch_for(rank: int, band_index: int) -> int:
    """How many of a rank-`rank` plant a hour at `band_index` yields, top band being 0.

    A negative index is an hour *above* the top band — see `band_index` — and the same
    arithmetic keeps climbing: the clamp that used to sit here was the plateau the table
    asked to have removed.
    """
    top = BATCH_TOP.get(int(rank), 2)
    return max(1, top - BATCH_STEP * int(band_index))


def dc_for(biome: str) -> int:
    return FORAGE_DC.get((biome or "").strip().lower(), DEFAULT_FORAGE_DC)


def over_bands(margin: int) -> int:
    """How many virtual bands above the top this margin reaches. 0 at the top band."""
    top_floor = BANDS[0][0]
    if margin < top_floor + OVER_STEP:
        return 0
    return (int(margin) - top_floor) // OVER_STEP


def band_for(margin: int) -> tuple:
    """(label, finds, ceiling lift, pristine) for how far the check beat the ground.

    Above the top band the label holds but the finds keep growing — `OVER_FINDS` more
    kinds per `OVER_STEP` of margin, without limit. The table itself is the only cap: an
    hour that asks for more species than grow here simply runs out, which is the wood
    being poor rather than the roll being wasted, and the batch bonus (`batch_for` with a
    negative index) still pays on everything that was found.
    """
    over = over_bands(margin)
    if over:
        floor, label, finds, lift, pristine = BANDS[0]
        return (label, finds + OVER_FINDS * over, lift, pristine)
    for floor, label, finds, lift, pristine in BANDS:
        if margin >= floor:
            return (label, finds, lift, pristine)
    return RUINED


def band_index(margin: int) -> int:
    """Which band this is, counting from the best. Feeds `batch_for`.

    Negative above the top band — margin 25 in a wood with a top floor of 20 is index
    -1, margin 30 is -2 — so `batch_for`'s `top - step * index` keeps rising instead of
    plateauing the moment the roll clears the best named band.
    """
    over = over_bands(margin)
    if over:
        return -over
    for i, (floor, *_rest) in enumerate(BANDS):
        if margin >= floor:
            return i
    return len(BANDS)


def check_mods(actor, level: int) -> list:
    """The modifiers on a foraging Survival check, in one place.

    Built here rather than inline in `forage_hour` because the dice popup shows the
    player a breakdown *before* the roll, and the engine applies the modifiers *after* —
    two call sites that must never disagree about what the herbalism level is worth.
    """
    mods = []
    if actor is not None:
        mods = list(actor.skill_modifiers("survival"))
        if int(level) > 0:
            from .dice import Modifier

            mods.append(Modifier(int(level), "herbalism"))
    return mods


def forage_hour(biome: str, level: int, rank_ceiling: int, dice, actor=None,
                face: int | None = None) -> dict:
    """One hour of looking, as one Survival check and what it turned up.

    The check is the character's own Survival, and the world class adds to it on top —
    an Herbalist knows where to look as well as what they are looking at. That bonus is
    the track's payoff on the ground, the way `attempts_for` is its payoff in yield.

    `face` is a d20 the player already rolled on the popup; the engine still owns the
    modifiers and the total. When it is None the engine rolls, which is what every hour
    after the first does — one session is one popup, not one per hour of an 18-hour day.
    """
    table = table_for(biome, rank_ceiling)
    dc = dc_for(biome)

    mods = check_mods(actor, level)
    if face is not None:
        roll = dice.given(face, mods, label=f"Foraging ({table.biome})")
    else:
        roll = dice.d20(mods, label=f"Foraging ({table.biome})", visibility="player")
    margin = roll.total - dc
    label, finds, lift, pristine = band_for(margin)

    # A better hour also reaches rarer things, but never past what the track allows: the
    # ceiling is what the character can *handle*, and luck does not teach them.
    hour_ceiling = min(rank_ceiling, rank_ceiling + lift) if lift else rank_ceiling
    if lift:
        hour_ceiling = min(len(WEIGHT), rank_ceiling + lift)
        table = table_for(biome, hour_ceiling)

    # `finds` is how many *kinds* the hour turns up, and each of them comes as a patch.
    # A distinct species per find, because eight rolls that all landed on Woundwart is one
    # plant found eight times rather than the eight the band promised — and a table with
    # fewer species than the band asks for simply runs out, which is the wood being poor
    # rather than the character being bad at this.
    index = band_index(margin)
    found: dict[str, int] = {}
    picks = []
    seen: set[str] = set()
    tries = 0
    while len(picks) < finds and tries < finds * 8:
        tries += 1
        pick = dice.roll("1d100", label=f"Foraging ({table.biome})", visibility="hidden")
        row = table.lookup(pick.total)
        if row is None:
            picks.append({"roll": pick.total, "found": None, "id": None, "count": 0})
            continue
        if row.ingredient_id in seen:
            continue
        seen.add(row.ingredient_id)
        count = batch_for(row.rank, index)
        picks.append({"roll": pick.total, "found": row.name,
                      "id": row.ingredient_id, "count": count, "rank": row.rank})
        found[row.ingredient_id] = found.get(row.ingredient_id, 0) + count

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
           actor=None, first_face: int | None = None) -> dict:
    """A foraging session of however many hours the player asked for.

    Hour by hour rather than one roll for the stretch. Each hour is its own check, so a
    long day is a spread of good and bad hours rather than a single verdict — and when
    something stops the character partway, the hours before it still happened.

    `first_face` is the player's own d20 from the popup, spent on the first hour; the
    engine rolls the rest of the day itself.
    """
    hours = max(1, int(hours))
    found: dict[str, int] = {}
    pristine: dict[str, int] = {}
    each = []

    for n in range(hours):
        hour = forage_hour(biome, level, rank_ceiling, dice, actor=actor,
                           face=first_face if n == 0 else None)
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
