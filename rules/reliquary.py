"""Create Reliquary Arms and Shields (Ultimate Magic), reworked for the enchanting circle
(feat loop b4-crafting).

The book (aonprd.com FeatDisplay, read 2026-11-26): "When you craft a magic weapon, magic
armor, or magic shield, you may add one casting of consecrate or desecrate as part of the
item crafting process. This increases the item's Price by 250 gp. The item becomes a
reliquary and can be used as a holy (or unholy) symbol divine focus of your deity. If you
cast consecrate or desecrate, your reliquary counts as a permanent fixture for that spell
while it remains in the spell's area."

Its prerequisite Craft Magic Arms and Armor is retired (owner 2026-11-22, `feats.RETIRED`);
the owner ruled 2026-11-26 that such feats are stripped of it and reworked. Here the circle
is the craft: at Bind, a holder able to cast the spell may add `reliquary` ("consecrate" or
"desecrate"). The casting is spent at Bind like any cast (its prepared copy or a slot,
`casting.cast_source`), the item's price rises by 250 gp (`magic_layer.market_price` reads
the binding), and the maker pays half of it in coin, as every item's making costs half its
price (CRB, Magic Item Creation). The binding records the spell, so the item card and every
reader can ask `of(record)`.
"""
from __future__ import annotations

FEAT = "create-reliquary-arms-and-shields"
SPELLS = ("consecrate", "desecrate")
PRICE_GP = 250
COST_CP = PRICE_GP * 100 // 2


def holds(actor) -> bool:
    from . import feats

    return FEAT in feats._held(actor)


def refusal(actor, spell_id: str, gear: str) -> str:
    """Why this Bind cannot add the casting, or ""."""
    from . import casting, goods, magic_layer
    from . import spells as spells_mod

    if not holds(actor):
        return f"{actor.name} does not have Create Reliquary Arms and Shields."
    if spell_id not in SPELLS:
        return "A reliquary takes consecrate or desecrate."
    if gear not in magic_layer.ARMS:
        return "Only a weapon, armour or a shield becomes a reliquary."
    spell = spells_mod.get(spell_id)
    if not casting.castable_now(actor, spell):
        return f"{actor.name} cannot cast {spell.name}."
    source = casting.cast_source(actor, spell)
    if source is None:
        return f"{actor.name} has not prepared {spell.name} today."
    if source.get("pool") and casting.pool_left(actor, source["pool"]) < int(
            source.get("cost") or 1):
        return f"{actor.name} has no spell slot left for {spell.name}."
    if goods.in_copper(getattr(actor, "purse", None) or {}) < COST_CP:
        return f"The reliquary costs {COST_CP // 100} gp more, and you cannot pay it."
    return ""


def spend(actor, spell_id: str) -> None:
    """The casting and the coin, at Bind. `refusal` was asked first."""
    from . import casting, goods
    from . import spells as spells_mod

    spell = spells_mod.get(spell_id)
    source = casting.cast_source(actor, spell) or {}
    if source.get("pool") and int(source.get("cost") or 0):
        actor.spend_pool(source["pool"], int(source["cost"]))
    if source.get("key"):
        casting.unprepare(actor, source["key"])
    actor.purse, _ok = goods.spend(dict(actor.purse or {}), COST_CP)


def of(record) -> str:
    """The spell a reliquary was made with, "" for any other item."""
    from . import magic_layer

    try:
        return str((magic_layer.magic_of(record).get("binding") or {}).get("reliquary") or "")
    except Exception:  # noqa: BLE001 - a record with no layer is no reliquary
        return ""
