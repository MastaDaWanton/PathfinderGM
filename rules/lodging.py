"""A room at an inn or a tavern: what it costs, who lets it, and whether it is paid for.

Known since 0.2.13 and measured again on the 2026-10-09 playtest: "I pay for a room" took
no coin. The requests lane (2026-10-16) routed "ask for a room" at an inn to `rest` and
said so — "what the bed costs is the rest door's (not charged yet, a known gap)". This is
the rest door's price.

The book (Core Rulebook, Table 6-9 "Food, Drink, and Lodging", and the "Inn stay"
description beside it; PZO1110, read 2026-10-16 at d20pfsrd's lodging table): an inn stay
is priced PER DAY, at three qualities —
  poor    2 sp  "a place on the floor near the hearth"
  common  5 sp  "a place on a raised, heated floor, the use of a blanket and a pillow"
  good    2 gp  "a small, private room with one bed, some amenities, and a covered chamber
                pot in the corner"
Meals are priced per day beside it (good 5 sp, common 3 sp, poor 1 sp) and are already
goods a tavern sells (`goods.GEAR`), so a room here is the bed and nothing else.

Which quality a place lets is the world's to say, as a word (docs/from-world-bible.md,
"Where beds are let": `play.places[].lodging` — not exported yet). Until it is, every
place that lets beds lets the common stay, the price `cards.BED_PRICE_CP` always quoted.

A room paid for is held for the day it was paid for: an `ActiveEffect` on the payer,
tagged `holds.room.<slug>` and timed in rounds, so a second sleep at the same inn that day
is not charged again and the hold evaporates on the clock like every timed thing (law 2).
A place the sleeper holds themselves (`holds.place.<slug>`, the `found` door) charges
nothing: it is theirs.
"""
from __future__ import annotations

# Copper, per day (CRB Table 6-9).
STAY_CP = {"poor": 20, "common": 50, "good": 200}
DEFAULT_STAY = "common"
# How long a paid room stays the payer's: the book's unit, one day.
HELD_MINUTES = 24 * 60
ORIGIN = "rule:inn-stay"


def kinds() -> frozenset[str]:
    """The place kinds that let beds: the settlement table's `lodging` slot (the tavern,
    the inn), without their article."""
    from . import schemes

    return frozenset(str(x).removeprefix("the ")
                     for x in schemes.PLACE_KINDS.get("lodging") or ())


def lets_beds(scene, at: str = "") -> bool:
    """Whether beds are let where the party stands (or at `at`): a generated tavern or
    inn, or a place founded with one of those kinds."""
    from . import keepers

    at = str(at or getattr(scene, "at", "") or "")
    if not at:
        return False
    return keepers.kind_of(at, getattr(scene, "founded", None) or ()) in kinds()


def quality(scene, at: str = "") -> str:
    """The stay this place lets: the world's word when it exports one, else common."""
    return DEFAULT_STAY


def price_cp(scene, at: str = "") -> int:
    return STAY_CP[quality(scene, at)]


def slug(at: str) -> str:
    """The whole place id as one tag segment, dots made safe. Not the `found` door's
    last-segment slug: two towns' founded taverns are both "…/the-tavern", and a room
    paid for in one was held in the other (seen live 2026-10-16: the tag came out
    `holds.room.the-tavern`)."""
    return str(at or "").replace(".", "-")


def tag(at: str) -> str:
    return f"holds.room.{slug(at)}"


def held(actor, at: str) -> bool:
    """Whether `actor` has a room paid for at `at` today."""
    return bool(at) and actor is not None and actor.has_state(tag(at))


def owns(actor, at: str) -> bool:
    """Whether the place is the sleeper's own (`holds.place.<slug>`)."""
    return bool(at) and actor is not None and \
        actor.has_state(f"holds.place.{str(at).rsplit('/', 1)[-1]}")


def hold(actor, at: str, name: str, rounds_per_minute: int):
    """Hold the room for the day, through the one applicator."""
    from .activeeffect import ActiveEffect

    return actor.apply_effect(ActiveEffect(
        name=f"a room at {name}", kind="situation", key=f"room:{at}",
        source=f"place:{at}", origin=ORIGIN, duration="rounds",
        rounds_left=HELD_MINUTES * int(rounds_per_minute), tags=(tag(at),)))
