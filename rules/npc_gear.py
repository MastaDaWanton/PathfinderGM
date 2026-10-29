"""What an NPC carries, by the Core Rulebook's own table, bought as real items.

CRB Chapter 14, Step 6: "Gear" (p. 454, read 2026-10-28): "outfit the character with gear
appropriate to his level ... Use the total gp value found on Table 14-9 ... spend the listed
amount on each category by purchasing as few items as possible. Leftover gold from any
category can be spent on any other category. Funds left over at the end represent coins
and jewelry carried by the character." The owner's ruling of 2026-10-28 is that loot is the
gear a creature carries, so this is also what the app's own people leave behind.

Bought as the game's own things, so every number reads them: a masterwork or enchanted
weapon or suit is a forge record (`forge_items.record_for_base`, its +N laid on by the
enchanter's own writer `magic_layer.write`), worn and read on its own swing and in its own
AC; potions and kit are goods in the pockets; the rest is coin.

Two choices this module makes, each forced by what exists:

- The **magic** column is spent on the weapon's and the armour's enhancement, half each.
  The magic-item catalogue holds weapon and armour properties and no wondrous items — no
  cloak of resistance or ring of protection to buy — and the table allows moving a column.
- **Shields stay plain.** A shield's enhancement is an armour-bonus channel of its own
  that the forged armour row does not fold, and a +1 shield read loose would be one more
  armour bonus beside the suit's.
"""
from __future__ import annotations

# Table 14-9: NPC Gear, by BASIC level (index 0 is 1st). (total, weapons, protection, magic,
# limited use, gear) in gp. "Heroic level" is the next row down: a heroic NPC (PC classes)
# of level N uses row N+1, and heroic 20 the row past basic 20.
TABLE_14_9 = [
    (260, 50, 130, 0, 40, 40), (390, 100, 150, 0, 40, 100), (780, 350, 200, 0, 80, 150),
    (1650, 650, 800, 0, 100, 200), (2400, 900, 1000, 0, 300, 200),
    (3450, 1400, 1400, 0, 450, 200), (4650, 2350, 1650, 0, 450, 200),
    (6000, 2700, 2000, 500, 600, 200), (7800, 3000, 2500, 1000, 800, 500),
    (10050, 3500, 3000, 2000, 1050, 500), (12750, 4000, 4000, 3000, 1250, 500),
    (16350, 6000, 4500, 4000, 1350, 500), (21000, 8500, 5500, 5000, 1500, 500),
    (27000, 9000, 8000, 7000, 2500, 500), (34800, 12000, 10500, 9000, 2800, 500),
    (45000, 17000, 13500, 11000, 3000, 500), (58500, 19000, 18000, 16000, 4000, 1500),
    (75000, 24000, 23000, 20000, 6500, 1500), (96000, 30000, 28000, 28000, 8000, 2000),
    (123000, 40000, 35000, 35000, 11000, 2000), (159000, 55000, 40000, 44000, 18000, 2000),
]

MASTERWORK_WEAPON = 300      # CRB, "Masterwork Weapons"
MASTERWORK_ARMOUR = 150      # CRB, "Masterwork Armor"
# Magic weapon and armour prices: the bonus squared times 2,000 / 1,000 (CRB Table 15-9,
# 15-3), the same arithmetic `magic_layer.market_price` charges.
WEAPON_PLUS = 2000
ARMOUR_PLUS = 1000

# The suits a class may buy, best last, by its archetype's proficiency.
SUITS = {
    "heavy": ["scale mail", "chainmail", "banded mail", "half-plate", "full plate"],
    "light": ["padded", "leather", "studded leather", "chain shirt"],
    "none": [],
}

# The kit the gear column buys first, cheapest first: a traveller's basics.
KIT = ["flint-and-steel", "rations", "bedroll", "rope", "backpack", "torch"]


def row(level: int, heroic: bool = False) -> tuple:
    i = max(0, min(len(TABLE_14_9) - 1, int(level) - 1 + (1 if heroic else 0)))
    return TABLE_14_9[i]


def _cost(table: str, key: str) -> float:
    from . import armour as armour_mod
    from . import weapons as weapons_mod

    if table == "weapon":
        return float(weapons_mod.get(key).get("cost_gp") or 0)
    return float(armour_mod.row(table, key).get("cost_gp") or 0)


def _plus_for(spend: float, base: float, mwk: int, per: int) -> int:
    """The largest +N whose price fits (masterwork included), up to +5; 0 for none."""
    n = 0
    while n < 5 and base + mwk + per * (n + 1) ** 2 <= spend:
        n += 1
    return n


def outfit(doc: dict, armour_kind: str, shield: bool, limited=("potion-of-cure-light-wounds",)
           ) -> dict:
    """The gear section of a build document, spent by Table 14-9 for its class and level:

        {"weapon": {"base", "masterwork", "enhancement"}, "armour": {...}, "shield": str,
         "pockets": [goods keys], "coin_gp": int, "spent_gp": int}
    """
    from . import classes as classes_mod
    from . import goods

    level = int(doc.get("level") or 1)
    heroic = str(doc.get("class") or "") not in classes_mod.npc_classes()
    total, w_gp, p_gp, m_gp, l_gp, g_gp = row(level, heroic)
    spent = 0.0

    weapon = str(doc.get("equipped") or (doc.get("weapons") or ["club"])[0])
    w_base = _cost("weapon", weapon)
    w_spend = w_gp + m_gp / 2
    plus = _plus_for(w_spend, w_base, MASTERWORK_WEAPON, WEAPON_PLUS)
    mwk = plus > 0 or w_base + MASTERWORK_WEAPON <= w_spend
    w_price = w_base + (MASTERWORK_WEAPON if mwk else 0) + WEAPON_PLUS * plus ** 2
    spent += w_price

    a_spend = p_gp + m_gp / 2
    suit = None
    suits = SUITS.get(armour_kind, [])
    sh_key = "heavy shield" if shield and armour_kind == "heavy" else ("light shield" if shield else "none")
    sh_price = _cost("shield", sh_key) if sh_key != "none" else 0.0
    for s in suits:
        if _cost("armour", s) + sh_price <= a_spend:
            suit = s
    armour = None
    if suit:
        a_base = _cost("armour", suit)
        a_plus = _plus_for(a_spend - sh_price, a_base, MASTERWORK_ARMOUR, ARMOUR_PLUS)
        a_mwk = a_plus > 0 or a_base + MASTERWORK_ARMOUR + sh_price <= a_spend
        armour = {"base": suit, "masterwork": a_mwk, "enhancement": a_plus}
        spent += a_base + (MASTERWORK_ARMOUR if a_mwk else 0) + ARMOUR_PLUS * a_plus ** 2
    spent += sh_price

    pockets: list[str] = []
    budget = float(l_gp)
    for key in limited:
        price = _price(key)
        while price and budget >= price and pockets.count(key) < 6:
            pockets.append(key)
            budget -= price
            spent += price
    budget = float(g_gp)
    for key in KIT:
        price = _price(key)
        if price is not None and budget >= price:
            pockets.append(key)
            budget -= price
            spent += price
    coin = max(0, int(total - spent))
    return {"weapon": {"base": weapon, "masterwork": bool(mwk), "enhancement": plus},
            "armour": armour, "shield": sh_key, "pockets": pockets,
            "coin_gp": coin, "spent_gp": int(spent), "table_gp": total, "table": True}


def trade_outfit(doc: dict) -> dict:
    """What someone who does not fight carries: the tool or weapon of the trade, a
    traveller's kit, no armour, and no table coin — their purse is the small one every
    townsperson's kit derives (`bestiary._assemble_kit`).

    The owner's ruling of 2026-10-28: Table 14-9 for the people who fight (and for rank),
    not for the trades. Read literally it gave a 1st-level farmer 250 gp and a 12th-level
    village priest 13,746 gp in coin, 886,593 gp across the 272 builds — robbing a farmer
    would have paid like a dungeon."""
    weapon = str(doc.get("equipped") or (doc.get("weapons") or ["club"])[0])
    pockets = [k for k in KIT if _price(k) is not None]
    spent = _cost("weapon", weapon) + sum(_price(k) for k in pockets)
    return {"weapon": {"base": weapon, "masterwork": False, "enhancement": 0},
            "armour": None, "shield": "none", "pockets": pockets, "coin_gp": 0,
            "spent_gp": int(spent), "table_gp": 0, "table": False}


def _price(key: str) -> float | None:
    """A good's price in gp, or None for a key the shops do not carry: the general store's
    gear (`goods.good`), then the potions and oils (`goods.potion_goods`), which `good`
    does not hold — the first run bought no potion at any level for that reason."""
    from . import goods

    g = goods.good(key) or next((p for p in goods.potion_goods() if p.key == key), None)
    return float(g.price_gp) if g is not None and g.price_gp else None


def records(gear: dict) -> list[dict]:
    """The forge records a gear section's weapon and suit are, laid on as the enchanter
    lays a +N (`magic_layer.write`): what `npc_builds.actor` wears."""
    from . import forge_items, magic_layer

    out = []
    for kind in ("weapon", "armour"):
        g = (gear or {}).get(kind)
        if not g or not (g.get("masterwork") or g.get("enhancement")):
            continue
        plus = int(g.get("enhancement") or 0)
        base = str(g["base"])
        label = f"+{plus} {base.replace('-', ' ')}" if plus else f"masterwork {base.replace('-', ' ')}"
        rec = forge_items.record_for_base(base, gear=kind,
                                          quality_index=forge_items.MASTERWORK_AT, name=label)
        if plus:
            rec = magic_layer.write(rec, {"enhancement": plus},
                                    binding={"quality_index": rec["quality_index"],
                                             "level": max(3, 3 * plus), "perks": {}})
        out.append(rec)
    return out
