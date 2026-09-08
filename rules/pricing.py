"""What a thing is worth.

Nothing the player *made* had a value anywhere. 352 of the 663 raw materials carry an
authored `price_gp` and the crafting bench reads it when you buy, but a tincture, an
elixir or a powder came off the bench carrying `potency`, `tier` and `rank` and no price
field at all — so the one thing a herbalist actually produces was the one thing the game
could not put a number on.

Measured in play, this is what that looked like: an elderly woman at a market stall was
asked to name a price for a satchel holding a potency-1,335 purified draught and thirty
other preparations, and she said ten gold for the lot. She was not being stingy. Nothing
had reached her — every turn of that haggle resolved to `narrate_only`, and the purse was
still empty after the player shook her hand on twenty-two gold.

**Tier sets the base, potency multiplies it, and the multiplication is sub-linear.**
A thousandfold spread in potency exists on one shelf — 1.25 for a plain Yarow elixir
against 1,335.61 for the Blackthorn draught the same character brewed — and neither
extreme can be allowed to set the scale for the other. Linear pricing makes the draught
worth more than every reward in the campaign put together; a flat price band throws away
the work that got it to 1,335. The exponent keeps both true at once: a masterwork is
plainly a treasure, and it does not end the economy.

**A bottle that does nothing is priced as a bottle that does nothing.** Over half the
preparations in the live save read "nothing the engine can run" — they carry no
executable spec, and no amount of potency makes them do anything. That is mechanically
detectable rather than a matter of taste, so it is detected: `specs` is empty or it is
not.
"""
from __future__ import annotations

# What a potency-1 thing of each rarity is worth, in gold. The ladder is the engine's
# five rungs — there is no epic or mythic — and the steps are roughly threefold, which is
# what keeps a rare find worth looking for without making common goods worthless.
TIER_BASE: dict[str, float] = {
    "common": 1.5,
    "uncommon": 6.0,
    "rare": 20.0,
    "exotic": 60.0,
    "legendary": 200.0,
}

# The sub-linear exponent, chosen by the table. At 0.75 a thousandfold potency gap
# becomes a roughly two-hundredfold price gap: the Blackthorn draught above lands near
# 1,300gp rather than 66,000gp, which is a treasure a town can react to rather than one
# no shop on the continent could buy.
POTENCY_EXPONENT = 0.75

# What an item with no executable effect is worth as a fraction of the same item with
# one. Not zero: a well-brewed bottle of something is still a well-brewed bottle, and it
# still took the ingredients. But it is not medicine, and selling it as medicine at a
# medicine price is the thing this factor exists to stop.
INERT_FACTOR = 0.25

# What a shop pays for what it buys, against what it charges for the same thing. The
# usual half, which is where a haggle has room to move.
SHOP_BUYS_AT = 0.5

# What the counter charges somebody the watch is looking for — THIS APP'S rule, not the
# book's. The Core Rulebook prices goods and never asks who is buying; Ultimate
# Campaign's Reputation and Fame runs from -100 to 100 and spends prestige for favours
# without touching a price. The video-game traditions split: Skyrim keeps a bounty per
# hold and never moves a merchant's prices, Fallout: New Vegas has merchants refuse the
# Vilified outright and charges nothing extra in between. Neither gives a "suspected"
# any teeth, and this app needs a lesser state that bites without shutting a door.
#
# So a markup, stated once here. Half again for a wanted character — the price of a
# stallholder's silence, and enough that a fugitive feels it on every jar without being
# unable to buy bread — and a quarter for the merely suspected. The counter's own
# refusal (`play/views.py`, the trade panel) is the harder answer for the wanted, and
# the markup is what the narrated road pays when nobody refuses. Applied to what a shop
# charges AND to what it pays: a fence pays a wanted man less for the same reason it
# charges him more.
WANTED_MARKUP = 1.5
SUSPECTED_MARKUP = 1.25


def markup_for(buyer, town) -> float:
    """What the counter multiplies by for this person, in this town. 1.0 for anybody
    the watch has nothing on. Asks the vocabulary through `states.standing_with_the_law`
    — never a tag spelled here — so the name cleared by one `remove_effects(source=...)`
    is a name cleared at every counter."""
    from . import states

    law = states.standing_with_the_law(buyer, town)
    if law == "wanted":
        return WANTED_MARKUP
    if law == "suspected":
        return SUSPECTED_MARKUP
    return 1.0


def _tier_base(tier: str) -> float:
    """Anything untiered is common. The only safe direction: a thing with no rarity
    should be cheap, not sold as a legendary."""
    return TIER_BASE.get(str(tier or "").strip().lower(), TIER_BASE["common"])


def _as_float(value, fallback: float = 1.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if out > 0 else fallback


def _does_something(item) -> bool:
    """Whether the engine can actually run this thing.

    Reads `specs`, which is the executable form, and not `effects`, which is the prose
    the specs were converted from. A jar can carry three lines of description and no
    spec at all — that is exactly the "nothing the engine can run" the bench prints —
    and pricing the prose would pay full medicine price for a bottle of nothing.
    """
    if isinstance(item, dict):
        return bool(item.get("specs"))
    return bool(getattr(item, "specs", None))


def _field(item, name, default=None):
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def worth(item, *, buyer=None, town="") -> float:
    """What one of these is worth on an open counter, in gold.

    An authored price wins outright. `price_gp` is a fact somebody wrote down about a
    real material — quicklime is 1gp because the catalogue says so — and a formula that
    overrode it would be guessing over the top of an answer it already had.

    `buyer` and `town` are who is asking and where: the counter marks a wanted or a
    suspected character up (`markup_for`). Left out, the answer is the open price —
    what the shelf is drawn against and what a catalogue prints.
    """
    return round(_open_worth(item) * markup_for(buyer, town), 2)


def _open_worth(item) -> float:
    authored = _field(item, "price_gp")
    if authored not in (None, "", 0):
        try:
            return max(0.0, float(authored))
        except (TypeError, ValueError):
            pass

    potency = _as_float(_field(item, "potency"), 1.0)
    price = _tier_base(_field(item, "tier")) * (potency ** POTENCY_EXPONENT)
    if not _does_something(item):
        price *= INERT_FACTOR
    # Round to the copper. Fractions of a copper are not money.
    return round(price, 2)


def what_a_shop_pays(item, *, seller=None, town="") -> float:
    """What a stallholder offers for it. Half, and a haggle moves from there — and
    less again from somebody the watch wants, by the same factor the shelf charges
    them more."""
    return round(_open_worth(item) * SHOP_BUYS_AT / markup_for(seller, town), 2)


def coin(gold: float) -> dict[str, int]:
    """Gold as the purse actually holds it: gp, sp, cp.

    Kept here rather than in the purse because a price is where fractions appear —
    a common inert preparation is worth about a third of a gold piece, and calling that
    "0 gp" would make a satchel of them free to take.
    """
    total_cp = int(round(max(0.0, float(gold or 0)) * 100))
    return {"gp": total_cp // 100, "sp": (total_cp % 100) // 10, "cp": total_cp % 10}


def as_text(gold: float) -> str:
    """"1,326 gp 4 sp" — what to print beside a thing."""
    c = coin(gold)
    parts = [f"{c['gp']:,} gp"] if c["gp"] else []
    if c["sp"]:
        parts.append(f"{c['sp']} sp")
    if c["cp"]:
        parts.append(f"{c['cp']} cp")
    return " ".join(parts) or "0 cp"
