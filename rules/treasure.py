"""What the dead were carrying.

The bestiary has carried a `treasure` field all along — 550 creatures declare one of the
Core Rulebook's classes (`none`, `incidental`, `standard`, `double`, `triple`) — and
nothing read it. That was invisible while buying was free. It stopped being invisible the
moment a market started charging: a character begins with their class's starting wealth,
spends it, and had no way on earth to get any more. The economy ran one direction only.

This is the third field tonight found declared and unread, after `starting_wealth` on
every class and `price_gp` on every material. They are worth looking for as a class of
bug: data written by one pass and never wired by the next.

**Values are the Core Rulebook's own** — Table: Treasure Values per Encounter, the NPC
Gear column rounded to the gold piece — so a fight pays what the book says a fight of
that CR pays. Rolled around that centre rather than paid flat, because a purse that is
always exactly 260 gp is a table nobody has to think about.

Settled where XP is settled, and for the same reason: two different pieces of code end
fights, and both have to pay out the same way.
"""
from __future__ import annotations

from . import dice as dice_mod

# Core Rulebook, Treasure Values per Encounter, "slow"/"medium" NPC gear column in gp.
# Index is CR; CR 0 and fractional CRs share the lowest rung, which is what the book does
# with them in practice.
_BY_CR: dict[int, int] = {
    0: 100, 1: 260, 2: 550, 3: 800, 4: 1150, 5: 1550, 6: 2000, 7: 2600, 8: 3350,
    9: 4250, 10: 5450, 11: 7000, 12: 9000, 13: 12000, 14: 15000, 15: 19500,
    16: 25000, 17: 32000, 18: 41000, 19: 53000, 20: 67000,
}

# What the creature's own entry says it is carrying, as a multiple of the CR value.
CLASSES: dict[str, float] = {
    "none": 0.0,
    "incidental": 0.5,
    "standard": 1.0,
    "double": 2.0,
    "triple": 3.0,
}

# A single creature is not a whole encounter. The book's table prices the *encounter*, so
# paying it per corpse would make a pack of six wolves six encounters' worth of gold.
PER_CREATURE = 0.25


def _entry(actor) -> dict:
    """This actor's bestiary entry, looked up the way `xp.worth` looks one up.

    An instantiated Actor carries neither `cr` nor `treasure` — those stay in the
    template it was stamped from — so reading the attributes off the actor answered ''
    and 0 for every creature in the game. Same resolution order as the XP award: the
    template link first, which is exact however the GM renamed the thing, then the
    display name slugified for creatures spawned before that link existed.
    """
    from . import bestiary

    # `everything()`, not `lookup()`. Lookup answers with the trimmed playable stat
    # block — hp, ac, saves, attacks — and drops the import's own columns, so it reports
    # `treasure = None` and `cr = None` for every creature in the game including the
    # 550 that declare one.
    corpus = bestiary.everything()
    tried = [str(getattr(actor, "from_template", "") or "").strip().lower()]
    name = str(getattr(actor, "name", "") or "").strip().lower()
    for bare in (name, name.removeprefix("the ").strip(), name.removeprefix("a ").strip()):
        if bare:
            tried.append(bare.replace(" ", "-"))
    for key in tried:
        found = corpus.get(key) if key else None
        if isinstance(found, dict):
            return found
    return {}


def _cr_of(actor) -> int:
    entry = _entry(actor)
    for source in (actor, entry):
        for attr in ("cr_value", "cr"):
            raw = (source.get(attr) if isinstance(source, dict)
                   else getattr(source, attr, None))
            if raw in (None, ""):
                continue
            try:
                return max(0, min(20, int(float(str(raw).split("/")[0].strip() or 0))))
            except (TypeError, ValueError):
                continue
    return 0


def class_of(actor) -> str:
    """The treasure class this creature declares, or "" when it declares nothing.

    Empty is not the same as `none`: 6,355 of the bestiary's 7,136 entries simply never
    had the column filled in, and treating silence as "carries nothing" would quietly
    make almost every fight in the game worthless. Silence means the GM decides, which
    is the same answer `xp.worth` gives for a creature with no price.
    """
    raw = str(getattr(actor, "treasure", "") or "").strip().lower()
    if not raw:
        raw = str(_entry(actor).get("treasure", "") or "").strip().lower()
    for name in CLASSES:
        if raw.startswith(name):
            return name
    return ""


_COIN_GP = {"cp": 0.01, "sp": 0.1, "gp": 1.0, "pp": 10.0}


def _item_gp(it: dict) -> float:
    """One printed piece's book price, in gp, by the table it was read from (the compiled
    record's `table`); 0 for a piece no table prices — never a guess."""
    from . import goods, materials, pricing
    from . import magicitem

    table = str(it.get("table") or "")
    key = str(it.get("key") or "")
    n = max(1, int(it.get("count") or 1))
    if table == "coin":
        return float(it.get("count") or 0) * _COIN_GP.get(key, 0.0)
    if table == "magic item":
        rid = magicitem.recipe_named(str(it.get("printed") or ""))
        row = materials.recipe(rid) if rid else None
        return n * float((row or {}).get("price_gp") or 0)
    if table in ("potion", "alchemy"):
        return n * float(pricing.book_price(key) or 0)
    if table == "gear":
        g = goods.good(key)
        return n * float(g.price_gp) if g else 0.0
    found = goods.known_item(key) if key else None
    if not found:
        return 0.0
    base = float(found.get("cost_gp") or 0)
    plus = int(it.get("enhancement") or 0)
    if table == "weapon":
        extra = (300 if it.get("masterwork") or plus else 0) + 2000 * plus ** 2
    elif table in ("armour", "shield"):
        extra = (150 if it.get("masterwork") or plus else 0) + 1000 * plus ** 2
    else:
        extra = 0
    return n * (base + extra)


def carried_gp(actor) -> int:
    """What the book prints this body carrying is worth, in gp: its compiled Gear and
    Other Gear lines (`compile_block`), which the loot hands over piece by piece
    (`bestiary._assemble_kit`). 0 for a body with no printed gear."""
    from . import bestiary, compile_block

    tpl = str(getattr(actor, "from_template", "") or "").strip().lower()
    if not tpl:
        return 0
    rec = compile_block.record_for(bestiary.raw_block(tpl) or {})
    return int(round(sum(_item_gp(it) for it in (rec or {}).get("carries") or ())))


def worth(actor, rng=None) -> int:
    """What this one body is carrying beyond its printed gear, in gp. 0 when it says
    nothing or says none.

    **Less what it is printed carrying.** The book's treasure value is the TOTAL a creature
    has — "'NPC gear' indicates the monster has treasure as normal for an NPC", and an NPC's
    gear is its treasure ("Encounters against NPCs typically award three times the treasure
    a monster-based encounter awards, due to NPC gear", CRB Placing Treasure) — and the loot
    hands that gear over as real things since 2026-10-28, its magic items since 2026-10-30.
    Paying this purse on top paid the printed gear twice. What the purse adds is only what
    the printed gear leaves of the value, and nothing when the gear already exceeds it."""
    kind = class_of(actor)
    # "Incidental" is lair treasure, never coin on the body: "half this standard value, and
    # then only within the confines of its lair" (Bestiary intro, Treasure), the rule
    # `bestiary._carries_no_coin` already reads for pockets. Playtest 2026-11-20 #17: a
    # clockwork spy ("incidental (gemstone worth 50 gp)") dropped 1 pp at the fight's end.
    if not kind or kind in ("none", "incidental"):
        return 0
    centre = _BY_CR.get(_cr_of(actor), 0) * CLASSES[kind] * PER_CREATURE
    if centre <= 0:
        return 0
    # Rolled around the centre: 50%–150%, so the same wolf is not the same purse twice.
    roll = (rng or dice_mod.Dice()).roll("2d6").total          # 2..12, centred on 7
    rolled = max(1, int(round(centre * (0.5 + (roll - 2) / 10.0))))
    carried = carried_gp(actor)
    if not carried:
        return rolled
    return max(0, rolled - carried)


def take_from_fallen(scene, pc, rng=None) -> tuple[int, list[str]]:
    """The gold a finished fight leaves on the ground, and who was carrying it.

    Shaped exactly like `xp.award_for_fallen`, and called beside it: only the fallen on
    a side the PC was not on, while the sides are still declared. A foe who fled or was
    spared keeps their purse, which leaves mercy costing something rather than paying.
    """
    if pc is None or not scene.sides:
        return 0, []
    total, names = 0, []
    for side, refs in scene.sides.items():
        if pc.ref in refs:
            continue
        for ref in refs:
            foe = scene.actors.get(ref)
            # The same reading as `xp.award_for_fallen`: half of "beaten" has full
            # hit points, and a petrified foe dropped its purse nowhere.
            if foe is None or (foe.hp > 0 and not foe.is_down):
                continue
            got = worth(foe, rng)
            if got:
                total += got
                names.append(foe.name)
    return total, names


# --- a hoard as things, not a sum ---------------------------------------------------------
#
# The owner, playtest 2026-11-23 O8: a haunted coffer held 150 gp "and nothing else ...
# money is nice but the preference should be to give it out in the form of items either
# jewels or weapons or potions etc." Ultimate Equipment's treasure generation says the same
# (legacy.aonprd.com/ultimateEquipment/appendix.html, read 2026-11-25): "Select a number of
# rewards whose total gold piece value is equal to the total value of the treasure", take
# "the largest reward her budget allows", then fill the rest with "lesser rewards and coins".
# Gems "can generally be traded for their full value" (types B and C), which is why a gem
# sells at its value (`pricing.what_a_shop_pays_for_goods`) where a sword sells at half.
#
# The rewards are the catalogue's own, at its own prices, so a looted thing is the same
# record a counter sells: the 44 classic potions and oils (`goods.potion_goods`), the
# scrolls, wands and wondrous items (`goods.magic_item_goods`), the plain weapons, suits and
# shields of the Core tables, and the gems of UE's grades (`GEMS`). Delivered through
# `goods.deliver`, so a looted potion is drinkable and a looted sword is swingable. No model
# names any of it.

# Ultimate Equipment's gem grades (same page): least semi-precious 5 + 2d4 gp, lesser
# 25 + 2d4 x 5, semi-precious 50 + 2d4 x 10, greater semi-precious 250 + 2d4 x 50, lesser
# precious 500 + 2d4 x 100, greater precious 2,500 + 2d4 x 500. Each grade at its mean
# (10, 50, 100, 500, 1,000, 5,000), so a gem's name is its price, wherever it is sold; a few
# of each grade's own stones, by the book's own names.
GEMS: dict[str, int] = {
    "agate": 10, "azurite": 10, "hematite": 10, "malachite": 10, "obsidian": 10,
    "tigereye": 10, "turquoise": 10,
    "bloodstone": 50, "carnelian": 50, "moonstone": 50, "onyx": 50, "peridot": 50,
    "zircon": 50,
    "amber": 100, "amethyst": 100, "garnet": 100, "jade": 100, "jet": 100,
    "tourmaline": 100,
    "aquamarine": 500, "opal": 500, "black pearl": 500, "topaz": 500,
    "emerald": 1000, "ruby": 1000, "sapphire": 1000,
    "star sapphire": 5000, "large diamond": 5000,
}

# The most separate rewards one hoard is laid out in: a chest of eleven things is a shop.
HOARD_MOST = 6

# The arms a hoard holds: the Core Rulebook's common weapons, suits and shields, by the
# tables' own keys. Measured on the first cut, which drew from every simple and martial
# row: a temple's coffer held a spring blade, an underwater light crossbow and a combat
# scabbard. A short list is the shape of UE's type E, which names armour and weapons a
# fighter carries rather than every row of the equipment chapter.
HOARD_ARMS = frozenset({
    "dagger", "light-mace", "heavy-mace", "morningstar", "spear", "longspear",
    "handaxe", "short-sword", "rapier", "scimitar", "battleaxe", "longsword", "warhammer",
    "greataxe", "greatsword", "falchion", "glaive", "halberd", "shortbow",
    "longbow", "light-crossbow", "heavy-crossbow",
    "studded leather", "chain shirt", "scale mail", "breastplate", "chainmail",
    "light shield", "heavy shield",
})


def gem_value(name: str) -> int | None:
    """A gem's value by its name ("a garnet", "Garnet"), or None for anything else."""
    low = " ".join(str(name or "").lower().split())
    for art in ("a ", "an "):
        low = low.removeprefix(art)
    return GEMS.get(low)


def _rewards() -> dict[str, list]:
    """(name, price, good id) by kind, cached: what a hoard is laid out from."""
    global _REWARDS
    if _REWARDS is None:
        from . import goods

        arms = [g for t in ("weapons", "armour", "shields") for g in goods.table_goods(t)
                if g.key in HOARD_ARMS]
        _REWARDS = {
            "potion": [(g.name, g.price_gp, g.id) for g in goods.potion_goods()],
            "magic": [(g.name, g.price_gp, g.id) for g in goods.magic_item_goods()
                      if g.price_gp > 0],
            "arms": [(g.name, g.price_gp, g.id) for g in arms],
            "gem": [(name, float(v), "") for name, v in GEMS.items()],
        }
    return _REWARDS


_REWARDS: dict | None = None


def good_of(good_id: str):
    """The catalogue good a hoard reward was laid out from, by its id, or None."""
    from . import goods

    pools = (goods.potion_goods(), goods.magic_item_goods(),
             *(goods.table_goods(t) for t in ("weapons", "armour", "shields")))
    return next((g for pool in pools for g in pool if g.id == good_id), None)


def hoard(rng, gp: int) -> tuple[dict[str, int], dict[str, str], int]:
    """A hoard of `gp` as things: ({name: count}, {name: good id}, the coin left over).

    UE's order: the largest reward the budget allows, then lesser ones. Each pick takes a
    kind at random among the kinds something still fits in, then one of the dearest third
    of what fits, so a hoard holds a few good things rather than a heap of cheap ones;
    what no reward fits is coin. A gem has no good id: it is carried by its name, and sold
    by its value (`gem_value`). `rng` is a `random.Random`, seeded by the caller, so the
    same chest holds the same things every time it is asked."""
    left = float(max(0, int(gp)))
    things: dict[str, int] = {}
    ids: dict[str, str] = {}
    pools = _rewards()
    for _ in range(HOARD_MOST):
        kinds = [k for k in sorted(pools) if any(p <= left for _n, p, _i in pools[k])]
        if not kinds:
            break
        fits = sorted((r for r in pools[rng.choice(kinds)] if r[1] <= left),
                      key=lambda r: (-r[1], r[0]))
        name, price, gid = fits[rng.randrange(max(1, len(fits) // 3))]
        things[name] = things.get(name, 0) + 1
        if gid:
            ids[name] = gid
        left -= price
    return things, ids, int(left)
