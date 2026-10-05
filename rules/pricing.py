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
    # A step-bench thing carries `potency` 1.0, because its strength is baked into the
    # effects the engine runs (rules/crafting.py, "THE STEP BENCH"); the strength itself
    # rides in `mults`, and that is what it is worth.
    mults = _field(item, "mults") or {}
    if isinstance(mults, dict) and mults.get("potency"):
        potency = _as_float(mults.get("potency"), potency)
    price = _tier_base(_field(item, "tier")) * (potency ** POTENCY_EXPONENT)
    if not _does_something(item):
        price *= INERT_FACTOR
    # "Worth more" (plan §2): the quality ladder's price column, x0.5 Crude to x3
    # Flawless and +0.5 a step beyond (content/rules/herbal-quality.json, §12).
    quality = _field(item, "quality")
    if quality is not None:
        from . import crafting

        try:
            price *= crafting.quality_mult("price", int(quality))
        except (TypeError, ValueError):
            pass
    # Round to the copper. Fractions of a copper are not money.
    return round(price, 2)


# --- what a raw material may cost: one rule over every catalogue ---------------------------
#
# The owner, 2026-10-05, after the shops lane had priced 22 unpriced staples at their
# nearest priced sibling (1 gp, water 1 cp): "probably most are fine until we get to
# enchanting essences, catalysts, and neutralizers and those should cost more. Also if
# something is legendary or gives better multipliers it should cost more".
#
# Measured before this, over the 434 authored prices in content/materials: the alchemist's
# three common catalysts (brewer's yeast, mother of vinegar, rennet) and its three
# neutralizers sat at 1-2 gp beside the water and the oak bark, slaked lime (neutralizer
# strength 2) cost exactly what the strength-1 neutralizers did, two rare dyes cost less
# than an uncommon one, and two rare enchanting vessels cost a third of a common one.
#
# **Authored prices stay authored.** `worth` above keeps reading `price_gp` outright: a
# catalogue price is a fact somebody wrote down, and the book's (mithral, adamantine, the
# masterwork surcharges) are facts the book wrote down. So the rule does not derive
# prices over the top of them; it CHECKS them, on load, and refuses an out-of-line one
# with the fix named (`material_price_problems`). Deriving was the rejected option: it
# would have rewritten 300-odd prices the owner had just called fine to fix a dozen, and
# it would have put every unpriced row on a counter — `price_gp` absent means "the world
# does not sell this" (`play/craft_views._price_cp`), and a derived price would erase that.
#
# **The rule: floor = rung × kind × strength step.**
# - The rung, `MATERIAL_FLOOR_GP`, steps ×5. PF1e's own tier ladder is the Core
#   Rulebook's gem grades (10 / 50 / 100 / 500 / 1,000 / 5,000 gp, alternating ×5 and ×2)
#   and its trade-goods metals step ×5 then ×10 (iron 1 sp, copper 5 sp, silver 5 gp, gold
#   50 gp, platinum 500 gp a pound); Monster Hunter World's same-rarity ores step about ×3.
#   ×5 is the middle of what the traditions publish, and it sits under this catalogue's
#   own step (its plain medians run 1 / 25 / 200 / 1,350 / 6,000), so a floor refuses the
#   outlier and not the shelf. Measured against the 434 prices as the owner saw them: ×10
#   refused 62 (adamantine dust, the diamond focus, every greater resistance essence...);
#   ×√10 refused 9 but put the legendary floor at 100 gp, under the rare median; ×5
#   refuses 11, every one of them the owner's list or a near neighbour of it.
# - The kind factor, `POWER_KIND_FACTOR`, is 5: Ultimate Campaign's downtime capital
#   prices Magic at 100 gp against Goods at 20 (Table 2-1, p. 77), the one published
#   PF1e ratio between "a thing that does magic" and "a thing". It applies to essences,
#   catalysts, inks, chalks, foci and anything that carries `neutralizer` — what the
#   owner named — and to nothing else, so water, vinegar, charcoal and bark stay cheap.
# - The strength step is how far a row's own number (`plus`, `capacity`, `neutralizer`,
#   a catalyst's `dc_mod`) runs above what its rung already pays for, and it multiplies
#   LINEARLY. Squared was tried first, because the book squares a magic bonus (Table
#   15-29: bonus² × 1,000): it put slaked lime, a common strength-2 neutralizer, at 20 gp
#   — above sal ammoniac and every other uncommon salt (15 gp), the very inversion this
#   rule exists to refuse. A neutralizer's strength is not a magic bonus, and the
#   no-inversions check below already makes each step cost strictly more than the last.
#   Nothing else in a row is a multiplier the bench reads; a quench mark's amount is a
#   small fixed mark, not a step.
#
# **And no inversions** (`_inversions`): within one catalogue and one kind, a rarer row is
# never cheaper than a commoner one, and a stronger row at the same or a higher rung costs
# strictly more than a weaker one. This is THIS APP'S invariant, not the traditions':
# Skyrim prices the one Jarrin Root in the world at 10 and Monster Hunter's rarity 5
# Rathalos Plate outsells its rarity 6 Scale+ — rarity there is a band, not a price. Here
# the owner ruled it ("if something is legendary ... it should cost more"), so it holds.
#
# Exempt, each for a stated reason: `book: true` rows (printed PF1e prices, which measure
# a per-item surcharge rather than the house rung — cold iron is ×2 iron and so cheaper
# than copper by the book); the book-faithful magic-item catalogue (`magic-items.json`,
# every price computed by the book's own formulas, `rules/magicitem.py`); and the free
# token, `goods.FREE_AT_A_COUNTER_GP` (1 cp), on a plain common row — water is given away,
# and a copper is the nearest a counter comes to free.
MATERIAL_FLOOR_GP: dict[str, float] = {
    "common": 1.0,
    "uncommon": 5.0,
    "rare": 25.0,
    "exotic": 125.0,
    "legendary": 625.0,
}
POWER_KINDS = frozenset({"essence", "catalyst", "ink", "chalk", "focus"})
POWER_KIND_FACTOR = 5.0
_RUNGS = tuple(MATERIAL_FLOOR_GP)


def _rank(tier) -> int:
    t = str(tier or "common").strip().lower()
    return _RUNGS.index(t) if t in _RUNGS else 0


def is_power_kind(row: dict) -> bool:
    """An essence, a catalyst, an ink, a chalk, a focus, or anything that neutralizes —
    what the owner named as costing more than the plain consumables."""
    try:
        neutral = int(row.get("neutralizer") or 0)
    except (TypeError, ValueError):
        neutral = 0
    return str(row.get("kind") or "") in POWER_KINDS or neutral > 0


def _strengths(row: dict) -> dict[str, int]:
    """The numbers a bench reads as "how strong", each as a step count from 1, by the
    group it can be compared within."""
    out: dict[str, int] = {}
    for field in ("plus", "capacity", "neutralizer"):
        try:
            n = int(row.get(field) or 0)
        except (TypeError, ValueError):
            n = 0
        if n > 0:
            out[field] = n
    try:
        dc = int(row.get("dc_mod") or 0)
    except (TypeError, ValueError):
        dc = 0
    if dc < 0:
        # −2 is a catalyst's ordinary help and −3 the strong one: one step and two.
        out["dc_mod"] = -dc - 1
    return out


def strength_step(row: dict) -> int:
    """How far a row's strongest number runs above what its rung already pays for.

    `plus` and `capacity` climb with the rung on purpose (Arcane Essence I is common, V
    legendary; a quartz focus holds one rank, a diamond five), so a rung-1 +1 or a
    rung-5 capacity 5 is step 1 — the rung has priced it. Slaked lime is a strength-2
    neutralizer on the common rung, and that extra strength is what the step charges."""
    rank = _rank(row.get("tier")) + 1
    return max([1] + [n - rank + 1 for n in _strengths(row).values()])


def material_floor(row: dict) -> float:
    """The least a raw material of this rung, kind and strength may be priced at, in gold."""
    floor = MATERIAL_FLOOR_GP[_RUNGS[_rank(row.get("tier"))]]
    if is_power_kind(row):
        floor *= POWER_KIND_FACTOR
    return round(floor * strength_step(row), 2)


def _authored(row: dict):
    raw = row.get("obtain")
    nested = raw if isinstance(raw, dict) else {}
    value = row.get("price_gp", nested.get("price_gp"))
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _exempt(row: dict) -> bool:
    return bool(row.get("book"))


def _a(word: str) -> str:
    return ("an " if word[:1].lower() in "aeiou" else "a ") + word


def _why_floor(row: dict) -> str:
    bits = [f"{_RUNGS[_rank(row.get('tier'))]} rung "
            f"{MATERIAL_FLOOR_GP[_RUNGS[_rank(row.get('tier'))]]:g} gp"]
    if is_power_kind(row):
        bits.append(f"x{POWER_KIND_FACTOR:g} for {_a(str(row.get('kind')))}"
                    + (" that neutralizes" if row.get("neutralizer") else ""))
    step = strength_step(row)
    if step > 1:
        bits.append(f"x{step} for its strength")
    return ", ".join(bits)


def material_price_problems(rows, source: str = "") -> list[str]:
    """Every authored price in one catalogue that breaks the rule, each with its fix named;
    [] when sound. `source` names the file in the message."""
    from . import goods

    where = f"{source}: " if source else ""
    priced = []
    out: list[str] = []
    for row in rows or ():
        if not isinstance(row, dict) or not row.get("id"):
            continue
        price = _authored(row)
        if price is None or price <= 0 or _exempt(row):
            continue
        priced.append((row, price))
        if price == goods.FREE_AT_A_COUNTER_GP and _rank(row.get("tier")) == 0 \
                and not is_power_kind(row):
            continue    # the free token: water, given away
        floor = material_floor(row)
        if price < floor:
            out.append(f"{where}{row['id']} is {_a(row.get('tier') or 'common')} "
                       f"{row.get('kind')} at {price:g} gp, under its floor of {floor:g} gp "
                       f"({_why_floor(row)}): raise its price_gp to at least {floor:g}.")
    out.extend(_inversions(priced, where))
    return out


def _inversions(priced, where: str) -> list[str]:
    out: list[str] = []
    by_kind: dict[str, list] = {}
    for row, price in priced:
        by_kind.setdefault(str(row.get("kind") or ""), []).append((row, price))
    # A rarer row never cheaper than a commoner one of its kind. Ties are allowed: a rung
    # is a coarse label, and the book itself puts gold and mithral at one price a bar.
    for kind, rows in by_kind.items():
        for row, price in rows:
            dearer = [(r, p) for r, p in rows
                      if _rank(r.get("tier")) < _rank(row.get("tier")) and p > price]
            if dearer:
                top, top_price = max(dearer, key=lambda x: x[1])
                out.append(f"{where}{row['id']} is {_a(str(row.get('tier')))} {kind} at "
                           f"{price:g} gp, cheaper than the {top.get('tier')} {top['id']} "
                           f"at {top_price:g} gp: a rarer {kind} never costs less. Raise "
                           f"{row['id']} to at least {top_price:g} gp, or, if a price is "
                           f"the book's, mark that row book: true.")
    # A stronger row at the same or a higher rung costs strictly more — slaked lime at 1 gp
    # neutralized twice what fuller's earth did at 1 gp. Compared across kinds: a
    # neutralizer is a neutralizer whether it is filed as a salt or a reagent.
    for row, price in priced:
        mine = _strengths(row)
        for other, other_price in priced:
            if other is row or _rank(row.get("tier")) < _rank(other.get("tier")):
                continue
            theirs = _strengths(other)
            for field in sorted(set(mine) & set(theirs)):
                if field == "plus" and row.get("family") != other.get("family"):
                    continue
                if mine[field] > theirs[field] and price <= other_price:
                    out.append(f"{where}{row['id']} has {field} {mine[field]} against "
                               f"{other['id']}'s {theirs[field]} and costs no more "
                               f"({price:g} gp against {other_price:g}): raise "
                               f"{row['id']} above {other_price:g} gp.")
                    break
    return out


# What a carried thing nobody priced is worth, in gold: THIS APP'S number, not the book's.
# The Core Rulebook prices what its tables list and says an item sells for "half its
# listed price" (p.140); for a thing with no listed price at all — a crate of somebody's
# cargo, a stranger's pack — no rule could be found (docs/items-have-owners.md, "could
# not confirm"). The answer is the bottom rung of the ladder above, the same one
# `_tier_base` gives anything untiered ("the only safe direction: a thing with no rarity
# should be cheap"), and it is the engine's: a model never names it (law 3). A world that
# says what its trade goods are worth would replace it (docs/from-world-bible.md).
UNLISTED_GP = TIER_BASE["common"]


def goods_worth(name: str) -> float:
    """What one of a carried thing is worth on an open counter, in gold, by its name.

    The Core tables first, at their printed prices: the general goods (`goods.GEAR`, by
    key or by the name the shelf gives it), then the weapon, armour and shield rows. A
    thing none of them lists is `UNLISTED_GP`. Never a price the fiction stated — that
    is the haggle, and `accept` can only lower what the rule gives."""
    from . import goods

    low = " ".join(str(name or "").split()).lower()
    for key, row in goods.GEAR.items():
        if low in (key, str(row.get("name", "")).lower()):
            return float(row.get("cost_gp") or 0) or UNLISTED_GP
    entry = goods.known_item(low)
    if entry and entry.get("cost_gp") not in (None, "", 0):
        try:
            return float(entry["cost_gp"])
        except (TypeError, ValueError):
            pass
    return UNLISTED_GP


def what_a_shop_pays_for_goods(name: str, *, seller=None, town="") -> float:
    """Half of `goods_worth`, less for somebody the watch wants: the same rule
    `what_a_shop_pays` applies to a jar off the bench, for a thing out of the pack."""
    return round(goods_worth(name) * SHOP_BUYS_AT / markup_for(seller, town), 2)


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
