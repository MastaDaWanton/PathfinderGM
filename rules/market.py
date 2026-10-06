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
    # One of a market's own counters keys its shelf and till by its kind (I2), and its
    # till is sized to what it sells (`till_tier`) — read here, so the panel's till, the
    # sale's `can_pay` and the shelf's bound are one answer whoever asks.
    if is_counter_kind(stall):
        tier = till_tier(stall, tier)
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
    # The staple consumables are sold too, and some of them are dug or gathered rather
    # than `obtain: bought` — coal, oak bark, curing salt — so the benches' "bought"
    # lists do not reach them. Every name a counter sells is a name the narrator and the
    # watcher must know.
    for m in consumables_of(tuple((_consumables_block().get("kinds") or {}))):
        seen.setdefault(str(getattr(m, "id", "")), m)
    _POOL = list(seen.values())
    return _POOL


_GOODS_ONLY = frozenset({"tavern", "inn", "alehouse", "taproom"})


def counter_kind_here(scene, stall: str = "") -> str:
    """What kind of counter the party is standing at, for what it stocks.

    One of the market's own counters when the stall says so (`market:armorer` — the
    trade panel keys its stall by the counter, `views._stall_of`); else the kind of the
    place whose keeper is here (`keepers.kind_of`), else a market — a peddler in the
    street sells what a market does."""
    from . import keepers

    if is_counter_kind(stall):
        return str(stall).lower()
    at = str(getattr(scene, "at", "") or "")
    if at and keepers.keeper_in(scene, at) is not None:
        return keepers.kind_of(at, getattr(scene, "founded", None) or ())
    return "market"


def on_sale(place: str, stall: str, day: int, taken: dict | None = None,
            tier: str = DEFAULT_STALL_TIER, counter_kind: str = "") -> list:
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
    from . import pricing

    # One of the market's own counters, or the stables: its staples, and the daily draw
    # from the benches its trade buys from. The till is sized to the counter (`till_tier`)
    # so it covers the dearest thing the counter makes — an armorer who could not have
    # paid for the full plate on her own rack is the "shop is a catalogue" bug again.
    kind = str(counter_kind or "").lower().removeprefix("the ")
    if is_counter_kind(kind):
        tier = till_tier(kind, tier)
        till = purse(place, stall, day, tier)
        staples = [g for g in staples_of(kind) if pricing.worth(g) <= till]
        tracks = draw_of(kind)
        if not tracks:
            return staples
        # A consumable that is a staple here is not drawn as well: it would sit on the
        # counter twice, and spend one of the quota's slots on a thing that is always
        # there anyway.
        held = {str(getattr(g, "id", "")) for g in staples}
        affordable = [m for m in priced_from(tracks)
                      if pricing.worth(m) <= till and str(getattr(m, "id", "")) not in held]
        shelf = stock(affordable, place=place, stall=stall, day=day)
        return staples + remaining(shelf, taken or {}, place, stall, day)

    till = purse(place, stall, day, tier)
    # The goods this counter always carries (`goods.goods_at`): staples, first on the
    # shelf and never sold out. A counter named by no kind (the old callers, the tests of
    # the material draw) keeps the draw alone.
    staples = []
    if counter_kind:
        from . import goods as goods_mod

        staples = [g for g in goods_mod.goods_at(counter_kind) if pricing.worth(g) <= till]
        if str(counter_kind).lower().removeprefix("the ") in _GOODS_ONLY:
            return staples
    # A place that names its benches (the smithy, the tannery) draws from them alone; any
    # other counter keeps the general draw.
    tracks = place_draw(counter_kind)
    held = {str(getattr(g, "id", "")) for g in staples}
    affordable = [m for m in (priced_from(tracks) if tracks else everything_priced())
                  if pricing.worth(m) <= till and str(getattr(m, "id", "")) not in held]
    shelf = stock(affordable, place=place, stall=stall, day=day)
    return staples + remaining(shelf, taken or {}, place, stall, day)


def summary(shelf) -> dict[str, int]:
    """How many of each rarity are on the shelf — for the page, and for a test to count
    without re-deriving the quota."""
    out: dict[str, int] = {}
    for m in shelf:
        t = tier_of(m)
        out[t] = out.get(t, 0) + 1
    return out


# --- the market's counters: shops, stalls, and the horse lines (I2) ----------------------------
#
# Measured on the 2026-09-28 playtest (item 10): a market was one person. `STAFFED["the
# market"]` stood "the stallholder who runs the pitch" behind it, and she was both the
# market's authority and the only seller the trade panel could open across — and she sold
# the general goods and nothing else, so of the 413 things the outfit page sells, the 366
# weapons, armours and shields were on no counter anywhere in the world once a campaign had
# begun.
#
# The shape is the one the traditions agree on (docs/design-d-people.md §2). Colchester's
# market, 1562: "Outsiders had standings assigned to them, according to their crafts",
# with the clerk of the market regulating and never trading. Mount & Blade's town: an
# armour dealer, an arms dealer, a horse dealer and a goods dealer, and a guildmaster who
# sells nothing. So: named shops for the big trades, stalls grouped by craft for the rest,
# and the master apart (`rules/audience.py`). The owner's split (2026-09-29): a village has
# the general store and stalls; a town or a city has the general store, an armorer, a
# weaponsmith and an alchemist, and stalls.
#
# **Nothing is stored.** Which counters a market has is a function of the settlement's id
# and scale, as its rooms are (`places._seed`): the stall lines are dealt onto the
# stallholders by lot, seeded on the settlement, so a town keeps its stalls in every session
# and two towns of one size differ. The keeper of each counter is minted only when the
# counter is first needed (`keepers.stand_up`), and a counter's kind carries its own
# contents — `market:stall-cloth-curios` is the stall that sells the cloth and curio lines —
# so a shelf can be drawn from the kind alone, by the engine's `buy`, with no world to hand.
from dataclasses import dataclass as _dataclass

_LINES: dict | None = None
_POOLS: dict | None = None

COUNTER_PREFIX = "market:"
STALL_PREFIX = "stall-"
STABLES_KIND = "stables"


def lines_doc() -> dict:
    """`content/rules/stall-lines.json`, read once, and refused with the fix named when its
    consumables block does not account for the catalogues (`consumable_problems`)."""
    global _LINES
    if _LINES is None:
        import json
        from pathlib import Path

        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "stall-lines.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        problems = consumable_problems(doc)
        if problems:
            raise ValueError("content/rules/stall-lines.json is refused: "
                             + " ".join(problems))
        # The counters sell at the catalogues' own prices, so the catalogues are held to
        # the one price rule before any counter opens (`pricing.material_price_problems`).
        problems = price_problems()
        if problems:
            raise ValueError("content/materials is refused: " + " ".join(problems))
        _LINES = doc
    return _LINES


def price_problems() -> list[str]:
    """Every shipped craft catalogue's authored prices against the one rule — rung, kind
    and strength, and no inversions (`pricing.material_price_problems`); [] when sound.

    Shipped catalogues only, as `consumable_problems` is: a homebrew price is the
    player's own to set, and refusing the app over one would lock them out of the very
    page that edits it. A world's `play.materials[]` rows go through the same function
    the day they have a reader (docs/from-world-bible.md)."""
    from . import materials as materials_mod
    from . import pricing

    out: list[str] = []
    for stem in materials_mod.CATALOGUES:
        craft = stem.removesuffix("-materials")
        out.extend(pricing.material_price_problems(_catalogue_rows(craft), f"{stem}.json"))
    return out


@_dataclass(frozen=True)
class Counter:
    """One counter at a market: a shop, a stall, or the horse lines.

    `id` is what the trade panel sends back (`line` on the wire, docs/fix-interfaces.md
    §2.10) and what the keeper's entity id ends in (`keeper:<market>#<id>`). `kind` is the
    counter kind the shelf is drawn by."""
    id: str
    label: str
    title: str
    words: tuple[str, ...]
    sort: str                 # "shop" | "stall" | "horses"
    says: str = ""

    @property
    def kind(self) -> str:
        return COUNTER_PREFIX + self.id


def _shops() -> list[dict]:
    return list(lines_doc().get("shops") or [])


def _stalls() -> list[dict]:
    return list(lines_doc().get("stalls") or [])


def _line(line_id: str) -> dict:
    return next((s for s in _stalls() if s.get("id") == line_id), {})


def _and(words: list[str]) -> str:
    words = [w for w in words if w]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def stall_lines(location, scale: str = "") -> list[list[str]]:
    """The stall lines this market's stallholders carry, one list per stallholder.

    Dealt by lot: the lines shuffled on a seed that is the settlement's own and nobody
    else's, then dealt round the table like cards, so every line lands on exactly one
    stall and a town of four stallholders folds five lines onto four people. The lot is
    `random.Random` on a string, which (unlike `hash`) is the same in every process."""
    from . import places as places_mod

    scale = scale or places_mod.scale_of(location)
    here = str(getattr(location, "id", None) or location or "nowhere")
    order = [s["id"] for s in _stalls()]
    if not order:
        return []
    wanted = int((lines_doc().get("holders") or {}).get(scale, len(order)) or len(order))
    n = max(1, min(len(order), wanted))
    dealt = list(order)
    random.Random(f"stall-lines|{here}").shuffle(dealt)
    hands = [dealt[i::n] for i in range(n)]
    # Each stall lists its lines in the document's order, so its id does not depend on
    # which card the dealer happened to turn first.
    return [sorted(h, key=order.index) for h in hands]


def _stall_counter(lines: list[str]) -> Counter:
    rows = [_line(x) for x in lines]
    nouns = [str(r.get("noun") or r.get("id")) for r in rows]
    return Counter(id=STALL_PREFIX + "-".join(lines),
                   label=f"the {_and(nouns)} stall",
                   title="the stallholder", words=("stallholder", "merchant", "trader"),
                   sort="stall", says=_and([str(r.get("says") or "") for r in rows]))


def _horses() -> Counter:
    doc = lines_doc().get("stables") or {}
    return Counter(id=str(doc.get("id") or "horses"),
                   label=str(doc.get("label") or "the horse lines"),
                   title=str(doc.get("title") or "the horse dealer"),
                   words=tuple(doc.get("words") or ("ostler", "handler")),
                   sort="horses", says="horses, ponies and mules, and their tack")


def has_stables(location) -> bool:
    """Whether the settlement has stables of its own to buy an animal at."""
    from . import places as places_mod

    try:
        return any(str(p.name).strip().lower() == "the stables"
                   for p in places_mod.home_set(location))
    except Exception:
        return False


def counters(location, *, stables: bool | None = None) -> tuple[Counter, ...]:
    """Every counter at this settlement's market, shops first, in the order the panel
    lists them.

    `location` is the world entity (its `scale` read through `places.scale_of`) or a
    bare id, which reads as a town — the same default the rest of the app takes. The horse
    lines stand at the market only where the settlement has no stables: where it has,
    the ostler sells the animals there (`goods_at("stables")`)."""
    from . import places as places_mod

    scale = places_mod.scale_of(location)
    at = places_mod.SCALES.index(scale) if scale in places_mod.SCALES else 1
    out: list[Counter] = []
    for shop in _shops():
        smallest = str(shop.get("smallest") or "village")
        if smallest in places_mod.SCALES and places_mod.SCALES.index(smallest) > at:
            continue
        out.append(Counter(id=str(shop["id"]), label=str(shop["label"]),
                           title=str(shop.get("title") or shop["label"]),
                           words=tuple(shop.get("words") or ()), sort="shop"))
    out.extend(_stall_counter(lines) for lines in stall_lines(location, scale))
    if not (has_stables(location) if stables is None else stables):
        out.append(_horses())
    return tuple(out)


def counter(location, counter_id: str) -> Counter | None:
    return next((c for c in counters(location) if c.id == str(counter_id or "")), None)


def is_counter_kind(kind: str) -> bool:
    kind = str(kind or "").lower().removeprefix("the ")
    return kind == STABLES_KIND or (kind.startswith(COUNTER_PREFIX)
                                    and bool(kind[len(COUNTER_PREFIX):]))


def _parts(kind: str) -> tuple[str, list[str]]:
    """("shop", [id]) / ("stall", [lines]) / ("horses", []) / ("", []) for a kind."""
    kind = str(kind or "").lower().removeprefix("the ")
    if kind == STABLES_KIND:
        return "horses", []
    if not kind.startswith(COUNTER_PREFIX):
        return "", []
    cid = kind[len(COUNTER_PREFIX):]
    if cid == _horses().id:
        return "horses", []
    if cid.startswith(STALL_PREFIX):
        known = {s["id"] for s in _stalls()}
        lines = [x for x in cid[len(STALL_PREFIX):].split("-") if x in known]
        return "stall", lines
    if any(s.get("id") == cid for s in _shops()):
        return "shop", [cid]
    return "", []


def _placed_gear() -> set[str]:
    """Every GEAR key some shop or stall line names."""
    out: set[str] = set()
    for row in _shops() + _stalls():
        out |= set(row.get("gear") or ())
    return out


def gear_of(kind: str) -> tuple[str, ...]:
    """The GEAR keys a market counter (or the stables) always has on it."""
    from . import goods as goods_mod

    sort, ids = _parts(kind)
    keys: list[str] = []
    if sort == "shop":
        keys = list(next((s for s in _shops() if s.get("id") == ids[0]), {}).get("gear") or ())
    elif sort == "stall":
        placed = _placed_gear()
        for line in ids:
            row = _line(line)
            keys += list(row.get("gear") or ())
            # A catalogue row no line names is still sold: the catch-all stall takes it,
            # so a GEAR row added tomorrow is on a counter tomorrow.
            if row.get("catch_all"):
                keys += [k for k in goods_mod.GEAR if k not in placed]
    return tuple(k for k in keys if k in goods_mod.GEAR)


def staples_of(kind: str) -> list:
    """What a market counter (or the stables) always carries, as `goods.Good`s: its GEAR,
    the Core tables it sells whole, or the animals and their tack."""
    from . import goods as goods_mod

    sort, ids = _parts(kind)
    if sort == "horses":
        return goods_mod.stables_goods()
    out = [g for g in (goods_mod.good(k) for k in gear_of(kind)) if g is not None]
    if sort == "shop":
        shop = next((s for s in _shops() if s.get("id") == ids[0]), {})
        for table in shop.get("tables") or ():
            out.extend(goods_mod.table_goods(str(table)))
    elif sort == "stall":
        # A stall sells a whole table too (the curio stall's enchanting manuals): lane F
        # built six manuals and no counter carried them, the 0.2.4 defect again — the
        # herbal and smithing manuals had shops, and stalls could only list GEAR.
        for line in ids:
            for table in _line(line).get("tables") or ():
                out.extend(goods_mod.table_goods(str(table)))
    out.extend(consumable_goods(consumables_at(kind)))
    return out


def draw_of(kind: str) -> tuple[str, ...]:
    """The crafting benches whose priced materials this counter draws a daily shelf from."""
    sort, ids = _parts(kind)
    rows = ([next((s for s in _shops() if s.get("id") == ids[0]), {})] if sort == "shop"
            else [_line(x) for x in ids] if sort == "stall" else [])
    out: list[str] = []
    for row in rows:
        for track in row.get("draw") or ():
            if track not in out:
                out.append(str(track))
    return tuple(out)


def priced_from(tracks) -> list:
    """Every material the named benches sell, once each (`everything_priced`, narrowed)."""
    global _POOLS
    if _POOLS is None:
        _POOLS = {}
    key = tuple(sorted(tracks or ()))
    if key not in _POOLS:
        from . import benches

        seen: dict[str, object] = {}
        for track in key:
            try:
                found = benches.obtainable(track, "bought")
            except Exception:
                continue
            for m in found:
                mid = str(getattr(m, "id", ""))
                if mid and mid not in seen and getattr(m, "price_gp", None):
                    seen[mid] = m
        _POOLS[key] = list(seen.values())
    return _POOLS[key]


# --- what the crafts burn: consumables, always on the counter --------------------------------
#
# The owner, 2026-10-05: "the most important thing for places like the smithy to sell are
# items to use as fuel for the furnace and other things consumed in crafting like water
# vinegar and alcohol". Before this a consumable reached a counter only through the daily
# draw, competing with every other common material of its bench for thirty slots: over 60
# days at a smithy's counter seeded on Panthcove, charcoal was on the shelf 30 days and
# quenching oil 29, the smithy sold silver ink and glass vials besides (its draw was every bench's), the
# alchemist sold charcoal, and the tannery had curing salt and oak bark on 0 days of 60 —
# both unpriced, so on no counter anywhere. A smith who could not buy fuel could not work.
#
# The traditions agree on the shape (content/rules/stall-lines.json, `consumables`):
# Skyrim's blacksmith chest always holds iron ingots and leather strips and only the rest
# is drawn; Stardew's Clint always sells coal and Pierre vinegar and oil, with randomness
# confined to the travelling cart; the Core Rulebook rolls its 75% for magic items and
# calls nonmagical goods "generally available". Potion Craft, whose traders' basics are
# random, is the measured counter-example — threads of players stuck for weeks without a
# basic ingredient.
#
# So the consumables are STAPLES: chosen by `kind` from the catalogues, never by name,
# common tier only, at the material's own price, never sold out, and out of the draw so
# the quota keeps all thirty slots for the things a shelf should be surprising about.
_CATALOGUE_ROWS: dict[str, list[dict]] | None = None


def _consumables_block(doc: dict | None = None) -> dict:
    return dict(((doc if doc is not None else lines_doc()).get("consumables")) or {})


def _catalogue_rows(craft: str) -> list[dict]:
    """The raw rows of one craft's shipped catalogue, `content/materials/<craft>-materials.json`.

    Raw rows rather than the bench's `Material`, because the question is what the document
    SAYS — its `kind`, its `tier`, its `price_gp` — and a loader that drops a field it has
    no slot for would answer it wrong. The bench's own object is fetched afterwards."""
    global _CATALOGUE_ROWS
    if _CATALOGUE_ROWS is None:
        _CATALOGUE_ROWS = {}
    if craft not in _CATALOGUE_ROWS:
        import json
        from pathlib import Path

        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "materials" / f"{craft}-materials.json"
        try:
            rows = json.loads(path.read_text(encoding="utf-8")).get("materials") or []
        except (OSError, ValueError):
            rows = []
        _CATALOGUE_ROWS[craft] = [r for r in rows if isinstance(r, dict) and r.get("id")]
    return _CATALOGUE_ROWS[craft]


def _row_price(row: dict):
    """A row's authored price, in either of the two shapes the shared shelf writes it
    (flat `price_gp`, or nested under `obtain`), or None."""
    nested = row.get("obtain") if isinstance(row.get("obtain"), dict) else {}
    price = row.get("price_gp", nested.get("price_gp"))
    try:
        return float(price) if price not in (None, "") and float(price) > 0 else None
    except (TypeError, ValueError):
        return None


def consumable_kinds(craft: str) -> frozenset:
    """The `kind`s one craft's working consumes, as the document files them."""
    return frozenset((_consumables_block().get("kinds") or {}).get(craft) or ())


def consumable_problems(doc: dict) -> list[str]:
    """Everything wrong with the consumables block, each with its fix named; [] when sound.

    Run on load (`lines_doc`): a kind nobody filed, a common consumable with no price, or
    a craft no market counter sells would each put a consumable on no counter anywhere,
    silently — the 0-of-60 curing salt was exactly that. Shipped catalogues only: a
    homebrew row has no craft of its own to be filed under."""
    block = _consumables_block(doc)
    kinds = block.get("kinds") or {}
    made = block.get("made_from") or {}
    tiers = set(block.get("tiers") or ())
    out: list[str] = []
    if not kinds:
        return ["It has no consumables.kinds: name the kinds each craft's working uses up."]
    for craft in sorted(set(kinds) | set(made)):
        rows = _catalogue_rows(craft)
        if not rows:
            out.append(f"consumables names {craft!r}, which has no "
                       f"content/materials/{craft}-materials.json: fix the craft's name.")
            continue
        used = set(kinds.get(craft) or ())
        other = set(made.get(craft) or ())
        both = used & other
        if both:
            out.append(f"{craft} files {sorted(both)} as both consumed and made_from: "
                       f"choose one.")
        present = {str(r.get("kind") or "") for r in rows}
        for k in sorted(present - used - other):
            out.append(f"{craft}-materials.json uses kind {k!r}, filed under neither "
                       f"consumables.kinds.{craft} nor consumables.made_from.{craft}: "
                       f"add it to one.")
        for k in sorted((used | other) - present):
            out.append(f"consumables files {craft} kind {k!r}, which no row of "
                       f"{craft}-materials.json has: remove it or fix the spelling.")
        for r in rows:
            kind = str(r.get("kind") or "")
            if r.get("consumed") and kind not in used:
                out.append(f"{r['id']} says consumed: true but its kind {kind!r} is not in "
                           f"consumables.kinds.{craft}: file the kind as consumed.")
            if kind in used and str(r.get("tier") or "common").lower() in tiers \
                    and _row_price(r) is None:
                out.append(f"{r['id']} is a {r.get('tier') or 'common'} {kind}, a staple, "
                           f"and has no price_gp: give it one in {craft}-materials.json.")
    sold = set()
    for row in list(doc.get("shops") or []) + list(doc.get("stalls") or []):
        sold |= set(row.get("consumables") or ())
    for craft in sorted(set(kinds) - sold):
        out.append(f"No shop or stall line sells {craft}'s consumables: add {craft!r} to "
                   f"some counter's `consumables`.")
    named = set(sold)
    for place, row in (block.get("places") or {}).items():
        named |= set((row or {}).get("consumables") or ())
    for craft in sorted(named - set(kinds)):
        out.append(f"A counter sells {craft!r} consumables, a craft consumables.kinds does "
                   f"not file: add it there or fix the spelling.")
    return out


def consumables_at(kind: str) -> tuple[str, ...]:
    """The crafts whose consumables this counter always carries: a market counter's from
    its shop or its stall lines, a place's (the smithy, the tannery) from `places`."""
    sort, ids = _parts(kind)
    if sort == "shop":
        rows = [next((s for s in _shops() if s.get("id") == ids[0]), {})]
    elif sort == "stall":
        rows = [_line(x) for x in ids]
    elif sort == "":
        place = str(kind or "").lower().removeprefix("the ")
        rows = [(_consumables_block().get("places") or {}).get(place) or {}]
    else:
        rows = []
    out: list[str] = []
    for row in rows:
        for craft in row.get("consumables") or ():
            if craft not in out:
                out.append(str(craft))
    return tuple(out)


def place_draw(kind: str) -> tuple[str, ...]:
    """The benches a settlement place's counter draws its daily shelf from, or () for the
    general draw. The smithy drew from every bench, and sold silver ink and glass vials."""
    place = str(kind or "").lower().removeprefix("the ")
    row = (_consumables_block().get("places") or {}).get(place) or {}
    return tuple(str(t) for t in row.get("draw") or ())


_CONSUMABLES: dict[tuple, list] | None = None


def consumables_of(crafts) -> list:
    """Every staple consumable of these crafts, as the bench's own `Material`s — what the
    forge's "Buy from the market" puts on its shelf, and what `consumable_goods` wraps for
    a counter. One answer for both, so the excursion and the trade panel cannot disagree
    about whether the collier has charcoal."""
    global _CONSUMABLES
    if _CONSUMABLES is None:
        _CONSUMABLES = {}
    key = tuple(sorted(set(crafts or ())))
    if key not in _CONSUMABLES:
        from . import benches

        tiers = {str(t).lower() for t in (_consumables_block().get("tiers") or ())}
        seen: dict[str, object] = {}
        for craft in key:
            kinds = consumable_kinds(craft)
            try:
                known = benches.module_for(craft).materials()
            except Exception:
                known = {}
            for row in _catalogue_rows(craft):
                mid = str(row["id"])
                if mid in seen or str(row.get("kind") or "") not in kinds:
                    continue
                if str(row.get("tier") or "common").lower() not in tiers:
                    continue
                m = known.get(mid)
                if m is None or _row_price(row) is None:
                    continue
                seen[mid] = m
        _CONSUMABLES[key] = sorted(seen.values(), key=lambda m: str(getattr(m, "name", "")))
    return _CONSUMABLES[key]


def consumable_goods(crafts) -> list:
    """`consumables_of` as goods on a counter: a staple (never sold out, `mark_sold`
    skipped), filed `kind="material"` so `goods.deliver` puts it in the satchel the
    benches read — the bare material id, the same key the excursion carries — and the
    trade window files it under materials."""
    from . import goods as goods_mod

    out = []
    for m in consumables_of(crafts):
        mid = str(getattr(m, "id", ""))
        out.append(goods_mod.Good(
            id=mid, name=str(getattr(m, "name", mid)),
            price_gp=float(getattr(m, "price_gp", 0) or 0) or goods_mod.FREE_AT_A_COUNTER_GP,
            tier=str(getattr(m, "tier", "common") or "common"), kind="material", key=mid))
    return out


def is_craft_material(item) -> bool:
    """Whether a thing off a shelf is one of the four crafts' materials — what a bench
    works from, which belongs in the satchel — rather than gear or a magic item. Read
    off the shipped catalogues, the ones `consumable_problems` holds to account."""
    global _CRAFT_IDS
    if _CRAFT_IDS is None:
        block = _consumables_block()
        crafts = set(block.get("kinds") or {}) | set(block.get("made_from") or {})
        _CRAFT_IDS = frozenset(str(r["id"]) for c in crafts for r in _catalogue_rows(c))
    return str(getattr(item, "id", "") or "") in _CRAFT_IDS


_CRAFT_IDS: frozenset | None = None


def till_tier(kind: str, tier: str = DEFAULT_STALL_TIER) -> str:
    """The till a counter keeps: at least `tier`, and rich enough at its poorest to have
    paid for the dearest thing it always carries.

    Derived, not written per counter: a table of tills would be a second answer to "what
    does the armorer sell", and the two would drift the day a price changed."""
    from . import pricing

    order = list(PURSE_BY_TIER)
    tier = str(tier or DEFAULT_STALL_TIER).lower()
    if tier not in order:
        tier = DEFAULT_STALL_TIER
    dearest = max((pricing.worth(g) for g in staples_of(kind)), default=0.0)
    for t in order[order.index(tier):]:
        if PURSE_BY_TIER[t][0] >= dearest:
            return t
    return order[-1]


def counter_for_want(want: str, choices, place: str, day: int, taken: dict | None = None):
    """(counter, good) for the thing the player asked for, across every counter here, or
    (None, None). The best fit wins (`goods.fit_rank`: the thing that IS the want, then
    the cheaper), as a shopkeeper reaches for the ordinary coil: "a coil of rope" is the
    general store's hemp — not the cord stall's silk, and not the weaponsmith's rope dart."""
    from . import goods as goods_mod

    best = (None, None, None)
    for c in choices:
        shelf = on_sale(place, c.kind, day, taken or {}, counter_kind=c.kind)
        found, _ = goods_mod.match_want(want, shelf)
        if found is None:
            continue
        rank = goods_mod.fit_rank(want, found)
        if best[0] is None or rank < best[2]:
            best = (c, found, rank)
    return best[0], best[1]


# --- the town forge, by the hour (blacksmithing plan §10, contracts §8) -------------------------
#
# A town smithy is rented, not bought from: the smith's furnace, fuel and anvil for as
# long as the work takes. One silver an hour, the plan's proposal and the UI plan's
# footer ("At Brannoc's smithy, 1 sp an hour"). For scale: the Core Rulebook's services
# table hires a trained hireling for 3 sp a DAY, so an hour at somebody else's furnace —
# charcoal included — is dear on purpose, the price of skipping the furnace you would
# otherwise have to own. Flat across village, town and city, as the Core table's
# services are; the till tiers above size what a counter can PAY, not what it charges.
#
# In copper, because the purse arithmetic is (`goods.spend` takes copper) and a rent of
# a tenth of an hour is a coin and a bit, never a fraction of a gold piece.
FORGE_RENT_CP_PER_HOUR = 10


def forge_rate(*, owned_by_party: bool = False) -> int:
    """Copper an hour at a smithy: nothing at the party's own, the town rate elsewhere.
    The one answer `places.smithy_here` puts in its `rate_cp_per_hour`."""
    return 0 if owned_by_party else FORGE_RENT_CP_PER_HOUR


def forge_rent(scene, hours: float, known=()) -> int:
    """What `hours` at the forge the party is standing in costs, in copper (contracts §8).

    Read off where the party is (`places.smithy_here`), never passed a rate: a caller
    that could name its own rate is a second answer to what the smith charges. Nothing
    when there is no smithy here, or it is the party's own.

    Charged for every copper's worth of time begun — the smith does not split a coin —
    so ten minutes is 2 cp, not 1.67 of one. Rounded to a millionth first so floating
    point cannot charge a copper for nothing: 10 × 0.1 is 1.0000000000000002 in binary,
    and a bare ceiling turns that one copper into two.

    `known` is passed through to `smithy_here` (`Engine.places()`), for an authored
    place whose id does not spell its name.
    """
    import math

    from . import places as places_mod

    try:
        h = float(hours or 0)
    except (TypeError, ValueError):
        return 0
    if not h > 0 or math.isinf(h):
        return 0
    here = places_mod.smithy_here(scene, known)
    if here is None:
        return 0
    return int(math.ceil(round(int(here["rate_cp_per_hour"]) * h, 6)))


def is_market(place_id: str, founded=()) -> bool:
    """Whether this place is a market with counters: the table's own "the market", or a
    place founded in play as one."""
    from . import keepers

    return keepers.kind_of(str(place_id or ""), founded) == "market"
