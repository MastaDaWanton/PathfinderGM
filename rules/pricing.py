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
    # An alchemical product is worth its book price (owner Q4.4, alchemy plan §12.4), never
    # the tier ladder: a potion of haste sold for 60 gp against the book's 750 before this.
    book = alchemy_worth(item)
    if book is not None:
        return book

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


# --- alchemy: what a product is worth, and what making one costs (alchemy plan §12.4, §5.9) ---
#
# **Worth.** The owner's Q4.4: book prices for book items, the tier ladder for house
# products. A classic (acid, alchemist's fire, antitoxin ...) is its formula row's printed
# price times the quality ladder's price column (Crude x0.5 .. Flawless x3,
# herbal-quality.json); a spell potion is the CRB's 50 gp x spell level x caster level
# (`formulae.potion_price`), and quality reaches it ONLY through caster level (owner, open
# point 6) — so the potion's own `caster_level` is read and nothing else multiplies. A house
# compound (no formula) keeps the ladder above. The shop pays half of either
# (`what_a_shop_pays`, unchanged).
#
# **The making cost.** Measured 2026-10-06 (lane H, tests/test_alchemy_prices.py), once
# formulae keyed on essences rather than materials (lane E): the cheapest legal set of
# BOUGHT inputs for a potion of haste is natron (1 gp), olive oil (1 gp) and a glass vial
# (1 gp) — 3 gp for a 750 gp potion that a shop buys back at 375. Every one of the 44 shipped
# potions but one came in at 2 to 32 gp, against the book's making cost of 25, 150 or 375.
# The "inputs over the fraction" lane D listed (rectified spirits at 25 gp, azoth at 1,500)
# were the OLD recipe sets; the formula table no longer asks for either.
#
# That is the failure the traditions document. Skyrim prices ingredients and nothing else,
# and its alchemy is the best-known money machine in the series ("ingredients are cheap to
# purchase while the resulting potions sell for substantially more": UESP, Skyrim:Making
# Money). Every tabletop tradition prices the raw materials as a FRACTION OF THE PRODUCT,
# in coin, whatever the materials are: PF1e Craft "pay 1/3 of the item's price for the raw
# material cost" and Brew Potion "raw materials ... one half this base price" (CRB); PF2e
# "raw materials worth at least half of the item's Price ... in a settlement, you can
# usually spend currency to get the raw materials" (Core, Craft); D&D 2024, materials cost
# half. Raising reagent prices instead was rejected: the essences a 750 gp potion keys on
# ride on 1 gp staples (natron, olive oil, quicklime) that a 2 gp antitoxin and every
# herbal tincture also use, so no reagent price could hold both ends.
#
# So the bench charges the book's making cost in coin at Bottle, LESS what the spent inputs
# are worth (`coin_to_make`): the reagents the formula names are part of what the coin
# buys, and a rare input the alchemist chose to spend counts toward it. The whole input bill
# of a formula product then lands at the book's fraction — never under it — however cheap
# the essences were to find. A house compound has no formula, sells on the ladder, and pays
# nothing extra. The bench (lane F) reads these; nothing here spends a coin.
CRAFT_FRACTION = 1 / 3       # CRB, Craft: "Pay 1/3 of the item's price for the raw material cost"
BREW_FRACTION = 1 / 2        # CRB, Brew Potion: raw materials cost "one half this base price"
ALCHEMY_CRAFT = "alchemist"  # rules/alchemist.py TRACK_ID: what a product of the bench is filed under

_CLASSIC_BY_NAME: dict[str, str] = {}


def _formula(row_or_fid):
    """A formula row from a row or an id; None for anything that is not one."""
    from . import formulae

    if isinstance(row_or_fid, dict):
        return row_or_fid if row_or_fid.get("kind") in formulae.KINDS else None
    return formulae.get(str(row_or_fid or "")) if row_or_fid else None


def _quality_index(item):
    """The quality ladder index of a product: `quality` on a Stock, `quality_index` on the
    bench's record (plan §12.2, where `quality` is the word). None when it has none."""
    for name in ("quality_index", "quality"):
        q = _field(item, name)
        if q is None or isinstance(q, bool):
            continue
        try:
            return int(q)
        except (TypeError, ValueError):
            continue
    return None


def book_price(row_or_fid, *, caster_level: int | None = None,
               quality_index: int | None = None) -> float | None:
    """A formula product's book price, in gold: a classic's printed price times the quality
    ladder's price column (Sound when none is given); a spell potion's 50 x spell level x
    caster level, at the row's own caster level unless one is given, with NO quality
    multiplier (open point 6: quality is already in the caster level)."""
    from . import formulae

    row = _formula(row_or_fid)
    if row is None:
        return None
    if row.get("kind") == "spell":
        cl = int(caster_level or row.get("caster_level") or 1)
        return round(formulae.potion_price(int(row.get("spell_level") or 0), cl), 2)
    try:
        price = float(row.get("price_gp") or 0)
    except (TypeError, ValueError):
        return None
    if quality_index is not None:
        from . import crafting

        price *= crafting.quality_mult("price", int(quality_index))
    return round(price, 2)


def _classic_named(name: str) -> str | None:
    """The classic formula a product is called after (bought acid is "Acid", the formula's
    own name), for a product whose record names no formula: an old save's bought jar, or a
    Stock, which has no `formula` field yet (lane F's record carries one, and it wins)."""
    from . import formulae

    if not _CLASSIC_BY_NAME:
        for fid, row in formulae.all().items():
            if row.get("kind") == "classic":
                _CLASSIC_BY_NAME[str(row.get("name") or "").strip().lower()] = fid
    return _CLASSIC_BY_NAME.get(" ".join(str(name or "").split()).lower())


def alchemy_worth(item) -> float | None:
    """What an alchemist's product is worth on an open counter, by the book; None for
    anything that is not one (a house compound, a herbal jar, a sword), which keeps the
    tier ladder. Read by `worth` and `what_a_shop_pays`, so the shelf and the sell-back are
    one answer.

    A product is the alchemist's (`craft`), or an old save's bought classic that no craft
    was ever written on — the counter sold it for 20 gp and the ladder bought it back for
    two silver."""
    from . import formulae

    craft = str(_field(item, "craft") or "")
    if craft not in (ALCHEMY_CRAFT, ""):
        return None
    sid = str(_field(item, "holds_spell") or "")
    if sid:
        if craft != ALCHEMY_CRAFT:
            return None     # a scroll or a wand holds a spell too, and is no potion
        row = formulae.for_spell(sid)
        if row is not None:
            level = int(row.get("spell_level") or 0)
        else:
            from . import spells

            try:
                sp = spells.get(sid)
            except KeyError:
                return None
            if sp.min_level is None:
                return None
            level = int(sp.min_level)
        try:
            cl = int(_field(item, "caster_level") or 0)
        except (TypeError, ValueError):
            cl = 0
        if cl <= 0:
            cl = int((row or {}).get("caster_level") or 0) or formulae.min_caster_level(sid, level)
        return round(formulae.potion_price(level, cl), 2)
    fid = str(_field(item, "formula") or "") or _classic_named(
        _field(item, "base") or _field(item, "name"))
    row = _formula(fid) if fid else None
    if row is None:
        return None
    if row.get("kind") == "spell":
        return book_price(row, caster_level=_field(item, "caster_level"))
    return book_price(row, quality_index=_quality_index(item))


def making_fraction(row_or_fid) -> float:
    """The book's raw-material fraction: half for a potion or oil holding a spell (Brew
    Potion), a third for a classic (Craft)."""
    row = _formula(row_or_fid)
    return BREW_FRACTION if (row or {}).get("kind") == "spell" else CRAFT_FRACTION


def making_cost(row_or_fid, *, caster_level: int | None = None) -> float:
    """What the raw materials of one formula product cost by the book, in gold: the
    fraction of its Sound price (a spell potion's at the caster level it is brewed at, so
    a Fine potion, one caster level up, costs what its higher price says). Quality above
    Sound raises what a classic is WORTH, not what it costs: the skill is the alchemist's."""
    row = _formula(row_or_fid)
    if row is None:
        return 0.0
    return round((book_price(row, caster_level=caster_level) or 0.0) * making_fraction(row), 2)


def spent_worth(spent) -> float:
    """What the inputs a step used up are worth, in gold: {material id: units}. A found or
    harvested material that no counter sells (no `price_gp`) is still worth its rung on the
    ladder (`worth`), so gathering saves a little; a catalyst or apparatus is never spent,
    and the caller leaves it out."""
    from . import materials

    total = 0.0
    for mid, n in dict(spent or {}).items():
        doc = materials.alchemy_doc(str(mid))
        if doc is None:
            continue
        total += worth(doc) * max(0.0, float(n or 0))
    return round(total, 2)


def coin_to_make(row_or_fid, spent_gp: float = 0.0, *, caster_level: int | None = None) -> float:
    """The coin Bottle takes for a formula product, in gold: the book's making cost less
    what the spent inputs are worth, never below nothing. A house compound (no formula)
    takes none."""
    return round(max(0.0, making_cost(row_or_fid, caster_level=caster_level)
                     - max(0.0, float(spent_gp or 0))), 2)


# What a family is bottled with (owner Q7.3: the vessel decides the family) and whether it
# needs a liquid to carry its essences: a drink, an oil and a splash flask are liquids, so a
# mix of solids needs a solvent dissolved into it (plan §7, Dissolve); a cloud's powder and
# a tool's stick do not. THIS LANE'S READING for the measurement below, not a bench rule:
# lane F's Bottle is the authority on what a mix must hold.
_LIQUID_FAMILIES = frozenset({"potion", "oil", "splash"})


def _working(doc: dict) -> set[str]:
    return {str(w.get("trait") if isinstance(w, dict) else w) for w in doc.get("working") or ()}


def _bought(doc: dict) -> float | None:
    p = doc.get("price_gp")
    try:
        return float(p) if p not in (None, "", 0) else None
    except (TypeError, ValueError):
        return None


def _carries(doc: dict) -> set[str]:
    return {str(t["essence"]) for t in doc.get("product") or ()
            if t.get("essence") and not t.get("drawback")}


def input_bill(row_or_fid, shelf: dict | None = None) -> dict:
    """The cheapest legal set of BOUGHT inputs for one formula product (plan §5.9): one unit
    of each material, enough carriers for every essence the formula requires at its grade,
    the cheapest vessel of its family, and the cheapest solvent when the family is a liquid
    and no chosen input pours. Catalysts and apparatus are never spent, so never counted; a
    material with no `price_gp` is found, never bought, and is left out.

    {"gp": float | None, "materials": [ids], "vessel": id | None, "medium": id | None,
     "unbuyable": [essences no priced material carries], "allowance": float,
     "book_gp": float, "over": bool}"""
    import itertools

    from . import formulae
    from . import materials as materials_mod

    row = _formula(row_or_fid)
    if row is None:
        return {}
    shelf = shelf if shelf is not None else materials_mod.alchemy_shelf()
    need = {str(e): int(g or 1) for e, g in
            (((row.get("requires") or {}).get("essences")) or {}).items()}
    family = str(row.get("family") or "")
    vessel_traits = set(formulae.VESSEL_FAMILIES)
    vessels, carriers, solvents = [], [], []
    for mid, doc in shelf.items():
        price = _bought(doc)
        if price is None:
            continue
        w = _working(doc)
        if w & {"catalyst", "apparatus"}:
            continue
        if w & vessel_traits:
            if any(family in formulae.VESSEL_FAMILIES[t] for t in w & vessel_traits):
                vessels.append((price, mid))
            continue
        if any(t.startswith("solvent:") for t in w):
            solvents.append((price, mid))
        if _carries(doc) & set(need):
            carriers.append((price, mid))
    vessels.sort()
    solvents.sort()
    carriers.sort()
    # Every essence's cheapest few carriers: a cover of k essences never needs more than k
    # materials, and the k cheapest of each are enough to find the cheapest cover.
    pool: list[tuple[float, str]] = []
    for e, g in need.items():
        for c in [c for c in carriers if e in _carries(shelf[c[1]])][: max(4, g + 2)]:
            if c not in pool:
                pool.append(c)
    unbuyable = sorted(e for e in need
                       if not any(e in _carries(shelf[m]) for _, m in carriers))
    book = book_price(row) or 0.0
    out = {"gp": None, "materials": [], "vessel": vessels[0][1] if vessels else None,
           "medium": None, "unbuyable": unbuyable, "book_gp": book,
           "allowance": round(book * making_fraction(row), 2), "over": False}
    if unbuyable:
        return out
    best = None
    for k in range(1, sum(need.values()) + 1):
        for combo in itertools.combinations(pool, k):
            have: dict[str, int] = {}
            for _, mid in combo:
                for e in _carries(shelf[mid]):
                    have[e] = have.get(e, 0) + 1
            if any(have.get(e, 0) < g for e, g in need.items()):
                continue
            cost = sum(p for p, _ in combo)
            medium = None
            if family in _LIQUID_FAMILIES and solvents and not any(
                    "liquid" in _working(shelf[m]) for _, m in combo):
                medium = solvents[0][1]
                cost += solvents[0][0]
            if best is None or cost < best[0]:
                best = (cost, [m for _, m in combo], medium)
    if best is None:
        return out
    gp = best[0] + (vessels[0][0] if vessels else 0.0)
    out.update(gp=round(gp, 2), materials=best[1], medium=best[2],
               over=gp > out["allowance"] + 1e-9)
    return out
