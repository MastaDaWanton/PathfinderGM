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

The columns, as the book defines them (CRB Step 6, aonprd Rules ID 359, read 2026-10-30):
"Weapons: ... normal, masterwork, and magic weapons"; "Protection: ... armor and shields,
as well as any magic item that augments a character's Armor Class or saving throws";
"Magic: ... all other permanent magic items. Most rings, rods, and wondrous items";
"Limited Use: ... alchemical items, potions, scrolls, and wands with few charges"; and
"Leftover gold from any category can be spent on any other category."

- **Weapons**: the weapon, masterwork and +N as far as the column goes.
- **Protection**: the suit and shield, then the protective wondrous items by slot — a cloak
  of resistance, a ring of protection, an amulet of natural armour (bracers of armour first
  for a class that wears no suit) — each the best +N the rest of the column buys, then the
  suit's own +N.
- **Magic**: the belt or headband of the build's best ability score.
- **Limited use**: cure potions, the dearest the column buys first (serious, moderate,
  light), six at most.
- Then the **leftover** of every column buys upgrades — the weapon's next +1, the next step
  of a worn item, the suit's — while one fits; what is left after that is coin.

Until 2026-10-30 the magic column went to the weapon and the suit and the docstring said
the catalogue had "no cloak of resistance or ring of protection to buy" — it had both. With
the protective column spent on a suit alone, 40% of the table's value across the 135
fighting builds was coin (579,384 of 1,445,900 gp): a 12th-level village priest carried
13,746 gp and a 20th-level captain 45,711 gp. The worn items are the catalogue's own
(`magicitem.finished`), worn on the body and dropped by it.

**Shields stay plain.** A shield's enhancement is an armour-bonus channel of its own that the
forged armour row does not fold, and a +1 shield read loose would be one more armour bonus
beside the suit's.
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

# The kit the gear column buys first, cheapest first: a traveller's basics. "flint and
# steel" is the general store's own key; "flint-and-steel" priced as nothing and was never
# bought.
KIT = ["flint and steel", "rations", "bedroll", "rope", "backpack", "torch"]

# The protective wondrous items by slot, the catalogue's names up to the "+N": what the
# Protection column buys after the suit (Step 6: "any magic item that augments a
# character's Armor Class or saving throws"), in this order.
PROTECTIVE = [("shoulders", "Cloak of Resistance"), ("ring", "Ring of Protection"),
              ("neck", "Amulet of Natural Armor")]
# For a class that wears no suit: bracers of armour first, an armour bonus of their own.
UNARMOURED = [("wrists", "Bracers of Armor")]
# The Magic column: the belt or headband of the best ability score.
STAT_ITEMS = {"str": "Belt of Giant Strength", "dex": "Belt of Incredible Dexterity",
              "con": "Belt of Mighty Constitution", "int": "Headband of Vast Intelligence",
              "wis": "Headband of Inspired Wisdom", "cha": "Headband of Alluring Charisma"}
# Limited use: the cure potions, dearest first, six at most (the first wiring's cap).
POTIONS = ["potion-of-cure-serious-wounds", "potion-of-cure-moderate-wounds",
           "potion-of-cure-light-wounds"]
MAX_POTIONS = 6


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


def outfit(doc: dict, armour_kind: str, shield: bool, limited=None
           ) -> dict:
    """The gear section of a build document, spent by Table 14-9 for its class and level:

        {"weapon": {"base", "masterwork", "enhancement"}, "armour": {...}, "shield": str,
         "pockets": [goods keys], "worn": [recipe ids], "coin_gp": int, "spent_gp": int}
    """
    from . import classes as classes_mod

    level = int(doc.get("level") or 1)
    heroic = str(doc.get("class") or "") not in classes_mod.npc_classes()
    total, w_gp, p_gp, m_gp, l_gp, g_gp = row(level, heroic)
    spent = 0.0
    pool = 0.0                    # every column's leftover, for the upgrade pass

    # Weapons.
    weapon = str(doc.get("equipped") or (doc.get("weapons") or ["club"])[0])
    w_base = _cost("weapon", weapon)
    plus = _plus_for(w_gp, w_base, MASTERWORK_WEAPON, WEAPON_PLUS)
    mwk = plus > 0 or w_base + MASTERWORK_WEAPON <= w_gp
    w_price = w_base + (MASTERWORK_WEAPON if mwk else 0) + WEAPON_PLUS * plus ** 2
    spent += w_price
    pool += w_gp - w_price          # below zero when the weapon itself costs more

    # Protection: the suit and shield, the protective items by slot, the suit's +N.
    suit = None
    suits = SUITS.get(armour_kind, [])
    sh_key = "heavy shield" if shield and armour_kind == "heavy" else ("light shield" if shield else "none")
    sh_price = _cost("shield", sh_key) if sh_key != "none" else 0.0
    for s in suits:
        if _cost("armour", s) + sh_price <= p_gp:
            suit = s
    left = p_gp - sh_price
    spent += sh_price
    armour = None
    if suit:
        a_base = _cost("armour", suit)
        a_mwk = a_base + MASTERWORK_ARMOUR <= left
        armour = {"base": suit, "masterwork": a_mwk, "enhancement": 0}
        cost = a_base + (MASTERWORK_ARMOUR if a_mwk else 0)
        spent += cost
        left -= cost
    worn: dict[str, tuple[float, str]] = {}          # slot -> (price, recipe id)
    for slot, name in (PROTECTIVE if suit else UNARMOURED + PROTECTIVE):
        best = _best(_ladder(name), left)
        if best:
            worn[slot] = best
            spent += best[0]
            left -= best[0]
    if armour and armour["masterwork"]:
        a_plus = _plus_for(left, 0, 0, ARMOUR_PLUS)
        armour["enhancement"] = a_plus
        spent += ARMOUR_PLUS * a_plus ** 2
        left -= ARMOUR_PLUS * a_plus ** 2
    pool += left

    # Magic: the belt or headband of the best ability.
    stat = STAT_ITEMS[_best_ability(doc)]
    stat_slot = "belt" if stat.startswith("Belt") else "headband"
    best = _best(_ladder(stat), m_gp)
    if best:
        worn[stat_slot] = best
        spent += best[0]
    pool += m_gp - (best[0] if best else 0)

    # Limited use: cure potions, dearest first.
    pockets: list[str] = []
    budget = float(l_gp)
    for key in limited or POTIONS:
        price = _price(key)
        while price and budget >= price and len(pockets) < MAX_POTIONS:
            pockets.append(key)
            budget -= price
            spent += price
    pool += budget
    budget = float(g_gp)
    for key in KIT:
        price = _price(key)
        if price is not None and budget >= price:
            pockets.append(key)
            budget -= price
            spent += price
    pool += budget

    # The leftover of every column ("can be spent on any other category"): the cheapest
    # step that fits, again and again — the weapon's next +1, a worn item's next rung or a
    # protective slot still bare, the suit's next +1 — so the gold becomes the gear the
    # table meant rather than a purse.
    weapon_doc = {"base": weapon, "masterwork": bool(mwk), "enhancement": plus}
    # Never past the row's total: the book's own 4th-level row prints columns summing to
    # 1,750 gp under a total of 1,650 (aonprd Rules ID 359, read 2026-10-30), and the first
    # run of this pass spent 1,656-1,729 gp on five 4th-level builds.
    pool = min(pool, total - spent)
    while pool > 0:
        steps = []
        if weapon_doc["enhancement"] < 5:
            n = weapon_doc["enhancement"]
            steps.append((WEAPON_PLUS * ((n + 1) ** 2 - n ** 2)
                          + (0 if weapon_doc["masterwork"] else MASTERWORK_WEAPON), "weapon",
                          None))
        if armour and armour["enhancement"] < 5:
            n = armour["enhancement"]
            steps.append((ARMOUR_PLUS * ((n + 1) ** 2 - n ** 2)
                          + (0 if armour["masterwork"] else MASTERWORK_ARMOUR), "armour",
                          None))
        for slot, name in ([] if suit else UNARMOURED) + PROTECTIVE + [(stat_slot, stat)]:
            have = worn.get(slot)
            nxt = next((r for r in _ladder(name) if r[0] > (have[0] if have else 0)), None)
            if nxt:
                steps.append((nxt[0] - (have[0] if have else 0), slot, nxt))
        fits = sorted((s for s in steps if s[0] <= pool), key=lambda s: (s[0], s[1]))
        if not fits:
            break
        cost, what, nxt = fits[0]
        if what == "weapon":
            weapon_doc.update(masterwork=True, enhancement=weapon_doc["enhancement"] + 1)
        elif what == "armour":
            armour.update(masterwork=True, enhancement=armour["enhancement"] + 1)
        else:
            worn[what] = nxt
        spent += cost
        pool -= cost
    coin = max(0, int(total - spent))
    return {"weapon": weapon_doc, "armour": armour, "shield": sh_key, "pockets": pockets,
            "worn": [rid for _, rid in (worn[s] for s in sorted(worn))],
            "coin_gp": coin, "spent_gp": int(spent), "table_gp": total, "table": True}


def _ladder(name: str) -> list[tuple[float, str]]:
    """The catalogue's rungs of one item, cheapest first, as (price gp, recipe id): every
    recipe called "<name> +N" (`materials.recipes`, retired rows left out)."""
    from . import materials

    want = name.lower() + " +"
    return sorted((float(r.get("price_gp") or 0), rid)
                  for rid, r in materials.recipes().items()
                  if str(r.get("name") or "").lower().startswith(want))


def _best(ladder: list[tuple[float, str]], budget: float) -> tuple[float, str] | None:
    """The dearest rung the budget buys, or None."""
    fits = [r for r in ladder if r[0] <= budget]
    return fits[-1] if fits else None


def _best_ability(doc: dict) -> str:
    """The build's highest final score (`npc_builds.final_scores`), ties to the earlier of
    Str, Dex, Con, Int, Wis, Cha."""
    from . import npc_builds

    scores = npc_builds.final_scores(doc)
    order = ("str", "dex", "con", "int", "wis", "cha")
    return max(order, key=lambda ab: (int(scores.get(ab, 10)), -order.index(ab)))


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
