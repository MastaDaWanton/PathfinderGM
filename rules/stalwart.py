"""Stalwart and Improved Stalwart (Advanced Class Guide; aonprd.com FeatDisplay.aspx?
ItemName=Stalwart and ...=Improved Stalwart, read 2026-11-27).

Stalwart: "While using the total defense action, fighting defensively action, or Combat
Expertise, you can forgo the dodge bonus to AC you would normally gain to instead gain an
equivalent amount of DR, to a maximum of DR 5/-, until the start of your next turn. This
damage reduction stacks with DR you gain from class features, such as the barbarian's, but
not with DR from any other source. If you are denied your Dexterity bonus to AC, you are
also denied this DR." Improved Stalwart: "Double the DR you gain from Stalwart, to a
maximum of DR 10/-."

Declared on the combat bar (the `stalwart` attack option beside Fight defensively or
Combat Expertise; Total defense (Stalwart) for the action), laid once the stance is: one
round's effect on the one ticker carrying an untyped penalty equal to the dodge forgone and
a `damage_reduction` payload with `stacks_with: "class"` — the shape orange war paint
already uses for "stacks with damage reduction gained via a character class"
(`Actor.damage_reduction`), and `needs_dex`, which that reader asks. Foundry PF1 models it
as a buff the player toggles by hand with both changes on it; this is the same record.
"""
from __future__ import annotations

from .activeeffect import ActiveEffect

FEAT = "stalwart"
IMPROVED = "defence.stalwart.improved"     # Improved Stalwart's tag
# The dodge bonuses Stalwart may trade, by the source each term carries.
TRADED = ("Fighting defensively", "Combat Expertise", "Total defense")


def held(actor) -> bool:
    from .class_abilities import feat_ids

    return FEAT in feat_ids(actor)


def dodge_forgone(actor) -> int:
    """The dodge bonus to AC the declared stances give right now."""
    return sum(m.value for m in actor.ac_modifiers()
               if m.type == "dodge" and m.source in TRADED and m.value > 0)


def convert(actor) -> list[str]:
    """Lay Stalwart's trade on a creature in one of the three stances; its tell."""
    n = dodge_forgone(actor)
    if n <= 0:
        return [f"{actor.name} has no dodge bonus from fighting defensively, total defense "
                f"or Combat Expertise for Stalwart to trade."]
    dr = min(10, 2 * n) if actor.has_state(IMPROVED) else min(5, n)
    actor.apply_effect(ActiveEffect(
        name="Stalwart", kind="damage_reduction", key="stalwart", source="Stalwart",
        origin="rule:feat-stalwart", duration="rounds", rounds_left=1,
        modifiers=[{"kind": "combat_mod", "target": "ac", "amount": -n, "bonus_type": "",
                    "note": "the dodge bonus forgone (Stalwart)"}],
        payload={"amount": dr, "bypass": "", "stacks_with": "class", "needs_dex": True}))
    return [f"{actor.name} stands stalwart: the +{n} dodge is given up for DR {dr}/— "
            f"until their next turn."]
