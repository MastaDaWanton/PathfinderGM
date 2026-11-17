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

## At the counter (2026-11-17)

Playtest 2026-11-17b #5/#9/#10: at a tavern, "a room for the night, and a hot meal" and
"I buy a meal and a drink" bought nothing, the keeper selling nothing at all. Prices
re-read that day at legacy.aonprd.com/coreRulebook/equipment.html, Goods and Services,
"Food, Drink, and Lodging": ale 4 cp a mug and 2 sp a gallon; inn stay per day good 2 gp,
common 5 sp, poor 2 sp; meals per day good 5 sp, common 3 sp, poor 1 sp; wine 2 sp a
pitcher, 10 gp a fine bottle. d20pfsrd's Hirelings, Servants & Services page prints the
stay "per night" at the same three prices, with the descriptions quoted above.

The keeper of an inn or a tavern now keeps a counter (`keepers.keeps_a_counter`): the
food and drink are goods on it (`goods.stocked_at`), and the three stays are rows of
`menu`, sold the way a temple's castings are (rules/services.py): the book's price moved
by the keeper's own terms, never haggled, through `Engine._buy_stay`, which holds the
room exactly as the rest door's bill does (`hold`). A stay bought at the counter makes
the night's sleep there free (`held`). Baldur's Gate's innkeepers sell their rooms by
tier off the same store screen as their drink (from memory, not re-checked); its rooms
heal more by tier, which the book does not do, so the three stays differ in price and
in the words alone.
"""
from __future__ import annotations

import re

# Copper, per day (CRB Table 6-9).
STAY_CP = {"poor": 20, "common": 50, "good": 200}
DEFAULT_STAY = "common"
# How long a paid room stays the payer's: the book's unit, one day.
HELD_MINUTES = 24 * 60
ORIGIN = "rule:inn-stay"
# A stay on the counter's screen: `service:inn-stay:<quality>`.
PREFIX = "service:inn-stay:"
# The book's own words for each stay (d20pfsrd, Hirelings, Servants & Services).
ABOUT = {"poor": "a place on the floor near the hearth",
         "common": "a place on a raised, heated floor, a blanket and a pillow",
         "good": "a small private room with one bed"}


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


def menu() -> list[dict]:
    """The stays a keeper lets, cheapest first: one row a quality, at the book's price.
    `name` carries how a bed is asked for, for the counter's matcher (`goods.match_want`:
    every word of the want in the row's name), as `services.menu` does for healing."""
    return [{"id": PREFIX + q, "quality": q, "cp": cp, "gp": cp / 100,
             "shown": f"A {q} room for the night ({ABOUT[q]})",
             "name": f"a {q} room or bed for the night, a night's lodging at the inn: "
                     f"{ABOUT[q]} (inn stay)"}
            for q, cp in sorted(STAY_CP.items(), key=lambda kv: kv[1])]


def find(want: str) -> dict | None:
    """The stay the words ask for, or None. A room asked for with no quality named is the
    common stay, the one the rest door charges (`DEFAULT_STAY`)."""
    from . import goods

    want = " ".join(str(want or "").split()).lower()
    rows = menu()
    if want.startswith(PREFIX):
        return next((r for r in rows if r["id"] == want), None)
    found, fits = goods.match_want(want, rows)
    if found is None:
        return None
    # "good" is one of the matcher's measure words ("a good rope"), so the quality is
    # asked of the want's own words here, against the book's three.
    said = set(re.findall(r"[a-z]+", want))
    q = next((q for q in STAY_CP if q in said), DEFAULT_STAY)
    return next((r for r in fits if r["quality"] == q), found)


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


def hold(actor, at: str, name: str, rounds_per_minute: int, stay: str = DEFAULT_STAY):
    """Hold the room for the day, through the one applicator."""
    from .activeeffect import ActiveEffect

    return actor.apply_effect(ActiveEffect(
        name=f"a {stay} room at {name}" if stay != DEFAULT_STAY else f"a room at {name}", kind="situation", key=f"room:{at}",
        source=f"place:{at}", origin=ORIGIN, duration="rounds",
        rounds_left=HELD_MINUTES * int(rounds_per_minute), tags=(tag(at),)))
