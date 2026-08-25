"""What one shop actually has on the shelf today.

Before this, "Buy from the market" drew from every material in the game that declared a
price — 397 of them at the alchemist's stall — so a single stallholder in Zhilvarnia
stocked adamantine, phoenix quill and every legendary catalyst at once, and the only
thing between the player and any of it was a d20. A shop that has everything is not a
shop; it is a catalogue with a shopkeeper standing in front of it.

A stall now carries a fixed shape of stock, thinning sharply as the rarity climbs:
thirty common things, twenty uncommon, fifteen rare, ten exotic, one legendary. **The
engine's ladder has five rungs — there is no "epic" or "mythic" tier** — so the six
bands that were asked for are mapped onto the five that exist, keeping the shape
(steeply decreasing) and the explicit "1 legendary". `QUOTA` is the one place to retune
it.

The stock is **drawn, not stored**. Seeding a `random.Random` on the place, the stall and
the day means the same shop on the same day always has the same shelf — walk out and back
in and the amethyst is still there — while tomorrow is a fresh roll, which is the "can be
rerolled every in game day" half. Nothing has to be written to the save for that, and a
save from before this feature opens with a full shelf rather than an empty one.

What *is* written down is what has been carried away: `Scene.market_taken` counts what
this shop has sold today, so the one legendary is one legendary. The key carries the day,
so yesterday's sales stop mattering on their own.
"""
from __future__ import annotations

import random

# The engine's rarity ladder, thinnest at the top. Anything a bench does not tier is
# treated as common, which is the only safe direction: a material with no rarity should
# be on the cheap end of the shelf, not sold as a legendary.
QUOTA: dict[str, int] = {
    "common": 30,
    "uncommon": 20,
    "rare": 15,
    "exotic": 10,
    "legendary": 1,
}

MINUTES_PER_DAY = 24 * 60


def day_of(clock_minutes: int) -> int:
    """Which day of the campaign this is. The shelf turns over on the boundary."""
    return int(clock_minutes or 0) // MINUTES_PER_DAY


def key(place: str, stall: str, day: int) -> str:
    """One shop, one day. Two stalls in one town are two different shelves — the
    ironmonger and the apothecary should not be selling from the same crate."""
    return f"{place or 'nowhere'}|{stall or 'stall'}|{day}"


def tier_of(material) -> str:
    tier = str(getattr(material, "tier", "") or "").strip().lower()
    return tier if tier in QUOTA else "common"


def stock(pool, *, place: str, stall: str, day: int) -> list:
    """Today's shelf at this stall, drawn from everything it could conceivably carry.

    Deterministic in (place, stall, day): the same shop on the same day is the same
    shelf. Sorted by rarity then name so the caller gets a stable order to show and to
    index into, rather than one that depends on how the pool was built.
    """
    rng = random.Random(key(place, stall, day))
    by_tier: dict[str, list] = {}
    for m in pool:
        by_tier.setdefault(tier_of(m), []).append(m)

    shelf: list = []
    for tier, want in QUOTA.items():
        have = sorted(by_tier.get(tier, []), key=lambda m: str(getattr(m, "id", "")))
        if not have:
            continue
        # `sample` rather than `choices`: a shelf holds thirty different common things,
        # not the same nail thirty times.
        shelf.extend(rng.sample(have, min(want, len(have))))
    order = list(QUOTA)
    shelf.sort(key=lambda m: (order.index(tier_of(m)), str(getattr(m, "name", ""))))
    return shelf


def remaining(shelf, taken: dict, place: str, stall: str, day: int) -> list:
    """The shelf minus what has already been carried out of the shop today."""
    k = key(place, stall, day)
    sold = {mid for mid, n in (taken or {}).items()
            if mid.startswith(k + "|") and n > 0}
    return [m for m in shelf if f"{k}|{getattr(m, 'id', '')}" not in sold]


def mark_sold(taken: dict, material_id: str, place: str, stall: str, day: int) -> None:
    """Record that this stall sold this thing today. Mutates `taken` in place."""
    k = f"{key(place, stall, day)}|{material_id}"
    taken[k] = int(taken.get(k, 0)) + 1


def summary(shelf) -> dict[str, int]:
    """How many of each rarity are on the shelf — for the page, and for a test to count
    without re-deriving the quota."""
    out: dict[str, int] = {}
    for m in shelf:
        t = tier_of(m)
        out[t] = out.get(t, 0) + 1
    return out
