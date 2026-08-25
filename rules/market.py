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


# --- what the stall can actually pay ---------------------------------------------------
#
# A market herbalist cannot hand over 1,325 gold for one bottle, and until this existed
# nothing said so: the shop's side of a trade was as unmodelled as the trade itself.
#
# Drawn the same way the shelf is — seeded on (place, stall, day) — so walking out and
# back in does not reroll the till, and tomorrow is a fresh day's takings. Nothing has to
# be written to the save for that.
#
# Generous, by instruction: "give everyone a good bit of coin". These are the float a
# stall has on hand, not its net worth, and the band is wide enough that two stalls in
# one town feel different to sell to.
PURSE_BY_TIER: dict[str, tuple[int, int]] = {
    "common": (40, 120),
    "uncommon": (150, 400),
    "rare": (500, 1200),
    "exotic": (1500, 3500),
    "legendary": (5000, 12000),
}

# What a stall is, when nothing says. A town market stall, which is what the player has
# actually been standing in front of every time this has come up.
DEFAULT_STALL_TIER = "uncommon"


def purse(place: str, stall: str, day: int, tier: str = DEFAULT_STALL_TIER) -> int:
    """What this stall has in the till today, in gold.

    Deterministic in (place, stall, day) exactly as `stock` is, and keyed apart from it —
    `stock` seeds a `Random` on the same string, and drawing both from one stream would
    make the shelf change whenever the purse formula was retuned.
    """
    lo, hi = PURSE_BY_TIER.get(str(tier or "").strip().lower(),
                               PURSE_BY_TIER[DEFAULT_STALL_TIER])
    return random.Random("purse|" + key(place, stall, day)).randint(lo, hi)


def spent_today(taken: dict, place: str, stall: str, day: int) -> float:
    """What this stall has already paid out today. Same shape as `mark_sold`."""
    return float((taken or {}).get(f"spent|{key(place, stall, day)}", 0) or 0)


def mark_spent(taken: dict, amount: float, place: str, stall: str, day: int) -> None:
    """Record coin leaving the till. Mutates `taken` in place, like `mark_sold`."""
    k = f"spent|{key(place, stall, day)}"
    taken[k] = round(float(taken.get(k, 0) or 0) + max(0.0, float(amount)), 2)


def can_pay(taken: dict, asked: float, place: str, stall: str, day: int,
            tier: str = DEFAULT_STALL_TIER) -> float:
    """What the stall can put on the counter against a price of `asked`.

    Capped, never refused. "i can still sell to them if i am willing to any get what they
    can give" — so a stallholder short of the asking price makes a smaller offer rather
    than turning the player away, and whether that is worth taking is the player's call.
    A caller that wants the refusal can compare this against `asked` itself.
    """
    left = purse(place, stall, day, tier) - spent_today(taken, place, stall, day)
    return round(max(0.0, min(float(asked or 0), left)), 2)


# --- the shelf a stall in play is standing behind --------------------------------------
#
# `craft_views` builds its pool per craft, because an excursion is a trip to *one* trade's
# supplier. A stall the player has walked up to in a scene is not that: it is whatever
# this stallholder sells, and the honest default is everything anybody prices.
#
# Cached per process rather than per call. Reading four benches' catalogues is the
# expensive part and the answer only changes when the content files do, which does not
# happen while the app is running.
_POOL: list | None = None


def everything_priced() -> list:
    """Every material any bench sells, once each.

    Deduplicated by id: `content/materials` is one shelf shared by four crafts, so the
    same quicklime is reachable from the alchemist and the blacksmith both, and a stall
    that stocked it twice would sell it twice.
    """
    global _POOL
    if _POOL is not None:
        return _POOL
    from . import benches

    seen: dict[str, object] = {}
    for track in benches.BENCHES:
        try:
            found = benches.obtainable(track, "bought")
        except Exception:
            continue
        for m in found:
            mid = str(getattr(m, "id", ""))
            price = getattr(m, "price_gp", None)
            if mid and mid not in seen and price:
                seen[mid] = m
    _POOL = list(seen.values())
    return _POOL


def on_sale(place: str, stall: str, day: int, taken: dict | None = None,
            tier: str = DEFAULT_STALL_TIER) -> list:
    """What this stall has on the counter right now — today's shelf minus what has gone.

    **A stall does not stock what it could not buy.** The rarity quota alone put a
    2,500 gp Ring of Climbing on a market stall's *common* shelf, because 18 of the 79
    common-tier materials are magic gear over 100 gp — the tiers track price well on
    average (common median 2 gp against legendary 16,000) and the tail is what gets you.
    A corner stall with 247 gp in the till holding a ring it could never have bought is
    the "shop is a catalogue" bug wearing a different hat.

    The till is the bound, and it is a bound this module already knows. One rule, no
    content re-tiering, and it makes the two halves of a shop agree: what a stallholder
    can pay out and what they have on the shelf are the same fact seen from both sides.
    """
    till = purse(place, stall, day, tier)
    from . import pricing

    affordable = [m for m in everything_priced() if pricing.worth(m) <= till]
    shelf = stock(affordable, place=place, stall=stall, day=day)
    return remaining(shelf, taken or {}, place, stall, day)


def summary(shelf) -> dict[str, int]:
    """How many of each rarity are on the shelf — for the page, and for a test to count
    without re-deriving the quota."""
    out: dict[str, int] = {}
    for m in shelf:
        t = tier_of(m)
        out[t] = out.get(t, 0) + 1
    return out
