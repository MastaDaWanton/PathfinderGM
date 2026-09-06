"""What else the ground has, when you go looking for herbs or ore.

"i go to collect herbs and run into a bear or a search for ore and find a massive vein
guarded by a cave worm." Ultimate Wilderness's foraging rules say the same thing more
quietly: check for a random encounter once per foraging expedition (AoN, Foraging,
optional rules). This is that check, rolled by the engine on its own dice once per
expedition, and it answers with one of four things:

  quiet     — the hours pass and the table said nothing more.
  rich      — a rich patch, a seam, a fallen trunk full of fungus: the yield doubles.
  creature  — something that lives here has noticed you. Animals and vermin come at
              you; the expedition is a fight now. Anything cleverer is in the way.
  guarded   — the best find of all, and something is sitting on it. The vein is real
              and it is booked; it is yours when whatever guards it is dead or gone.

The creature is never invented. It is drawn from the shipped bestiary by the biome the
scene stands on and a CR window around the character's level (`bestiary.search`), so
a forest at first level gives up a wolf and a mountain at fifth a cave worm's kind,
and nothing that the book does not put there. The table itself is authored once and
is not per biome: the biome comes in through the creatures, which is where it lives.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import bestiary

# The d100 bands, low to high. Authored to Ultimate Wilderness's temper — most
# expeditions are just work — with the guarded find rare enough to be a story.
BANDS = (
    (1, 55, "quiet"),
    (56, 75, "rich"),
    (76, 93, "creature"),
    (94, 100, "guarded"),
)

# Creature types that come at you on sight. The rest — dragons, fey, humanoids — are
# an obstacle with a mind, and the player gets to decide what to do about them.
AGGRESSIVE = frozenset({"animal", "vermin", "magical beast", "ooze", "plant"})

# The CR window around the character's level, and how far it stretches for the thing
# guarding the big find. A first-level character foraging should meet CR 1/3 to CR 2,
# not a CR 8 — the table is a hazard of the work, not a way to die of botany.
BELOW, ABOVE, GUARD_ABOVE = 2, 1, 2

# What multiplies the yield. A rich patch is twice the finding; a guarded find, three
# times, and it waits.
RICH_YIELD, GUARDED_YIELD = 2, 3


@dataclass
class Encounter:
    kind: str                       # quiet | rich | creature | guarded
    roll: int
    creature: dict | None = None    # the bestiary row, when there is one
    aggressive: bool = False
    yield_times: int = 1
    tell: str = ""
    extras: dict = field(default_factory=dict)


def _cr_window(level: int, guarding: bool) -> tuple[float, float]:
    low = max(1 / 3, level - BELOW)
    high = max(1, level + (GUARD_ABOVE if guarding else ABOVE))
    return low, high


def creature_for(biome: str, level: int, dice, guarding: bool = False) -> dict | None:
    """A bestiary row that lives here and is a fair match, or None when the book has
    nothing for this ground — a stone shelf where no creature is tagged is quiet."""
    low, high = _cr_window(level, guarding)
    rows = bestiary.search(biome=biome, cr_min=low, cr_max=high, limit=400)
    # Things that are only "any" for this biome are the second choice; specialists
    # first, so a forest gives up a wolf before a generic humanoid.
    rows = [r for r in rows if r.get("cr_value") is not None
            and r.get("creature_type") not in ("humanoid", "outsider", "undead")]
    if not rows:
        return None
    pick = dice.roll(f"1d{len(rows)}", label="what lives here", visibility="hidden").total
    return rows[pick - 1]


def roll(biome: str, level: int, dice) -> Encounter:
    """Once per expedition. The d100 is the engine's, hidden, like every other roll a
    player could not have known the number of."""
    r = dice.roll("1d100", label="the ground's own answer", visibility="hidden").total
    kind = next(k for lo, hi, k in BANDS if lo <= r <= hi)
    if kind == "quiet":
        return Encounter("quiet", r)
    if kind == "rich":
        return Encounter("rich", r, yield_times=RICH_YIELD)
    row = creature_for(biome, level, dice, guarding=(kind == "guarded"))
    if row is None:
        # Nothing lives here that the book prices for this level; the ground is
        # quiet, and a rich find is what a guarded one becomes with nobody on it.
        return (Encounter("rich", r, yield_times=RICH_YIELD) if kind == "guarded"
                else Encounter("quiet", r))
    aggressive = kind == "creature" and row.get("creature_type") in AGGRESSIVE
    return Encounter(kind, r, creature=row, aggressive=aggressive,
                     yield_times=GUARDED_YIELD if kind == "guarded" else 1)


def describe(enc: Encounter, what: str) -> str:
    """The tell's clause for the encounter. `what` is what was being gathered —
    "herbs", "ore" — so the rich find reads as a patch or a seam."""
    if enc.kind == "rich":
        return (f"The ground here is generous: a rich seam of {what}, and the haul is "
                f"twice what it would have been." if what == "ore" else
                f"A rich patch of {what}, thick enough to double the haul.")
    if enc.kind == "creature" and enc.creature:
        name = enc.creature["name"]
        return (f"Something has noticed the work: {_an(name)} comes out of the "
                f"{'rock' if what == 'ore' else 'undergrowth'}, and it is coming for you."
                if enc.aggressive else
                f"Something is in the way: {_an(name)} has the ground you wanted, and "
                f"has not moved off it.")
    if enc.kind == "guarded" and enc.creature:
        name = enc.creature["name"]
        return (f"The find of a lifetime — {'a massive vein of' if what == 'ore' else 'a whole hollow of'} "
                f"{what}, three times any ordinary haul — and {_an(name)} sitting on it. "
                f"It is yours when that is dead or gone.")
    return ""


def _an(name: str) -> str:
    return f"an {name}" if name[:1].lower() in "aeiou" else f"a {name}"
