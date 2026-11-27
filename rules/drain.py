"""Negative levels: energy drain applied (feat loop b7-small, 2026-11-27).

The book (aonprd.com, Special Abilities, "Energy Drain and Negative Levels", read
2026-11-27): "For each negative level a creature has, it takes a cumulative -1 penalty on
all ability checks, attack rolls, combat maneuver checks, Combat Maneuver Defense, saving
throws, and skill checks. In addition, the creature reduces its current and total hit
points by 5 for each negative level it possesses. The creature is also treated as one
level lower for the purpose of level-dependent variables (such as spellcasting) for each
negative level possessed. Spellcasters do not lose any prepared spells or slots as a
result of negative levels. If a creature's negative levels equal or exceed its total Hit
Dice, it dies." Temporary ones: "a new saving throw to remove the negative level each day
... The DC of this save is the same as the effect that caused the negative levels."
Energy drain (Universal Monster Rules): "the creature that inflicts it gains 5 temporary
hit points ... for each negative level it bestows".

The shape (the three laws): one ActiveEffect per negative level, its terms untyped
penalties through the modifier funnel — penalties always stack, so three levels are -3 —
and its daily save a `periodic` entry the one executor runs (`Actor.run_periodic`, per
day: `shed_save`). Remove the effect and its numbers go with it. The enervation family's
effectspec type stayed `engine=False` before this because "applying seven of [eight
numbers] would be worse than applying none"; all eight are here except "level-dependent
variables" beyond caster level, which nothing on the sheet reads as one number (said in
the effect's note).

Prior art: Foundry PF1 keeps negative levels as one number on the actor that its
formulas subtract (`attributes.energyDrain`), the CRB's own bookkeeping; one effect per
level is chosen here instead so each keeps its own DC and its own daily save, which a
single number cannot.
"""
from __future__ import annotations

from .activeeffect import ActiveEffect

TAG = "state.drained.negative-level"
KEY = "negative level"


def _terms() -> list[dict]:
    """One negative level's numbers, each an untyped -1 (-5 hit points)."""
    out = [{"kind": "combat_mod", "target": t, "amount": -1, "bonus_type": "",
            "note": KEY}
           for t in ("attack", "cmb", "cmd", "initiative", "caster_level", "spell_cl",
                     "str_check", "dex_check", "con_check", "int_check", "wis_check",
                     "cha_check")]
    out += [{"kind": "save_mod", "target": s, "amount": -1, "bonus_type": "", "note": KEY}
            for s in ("fort", "ref", "will")]
    out.append({"kind": "skill_mod", "target": "all", "amount": -1, "bonus_type": "",
                "note": KEY})
    out.append({"kind": "combat_mod", "target": "hp_max", "amount": -5, "bonus_type": "",
                "note": KEY})
    return out


def count(actor) -> int:
    return sum(1 for e in actor.effects if TAG in (e.tags or ()))


def lay(actor, n: int, dc: int | None, source: str, origin: str,
        permanent: bool = False, once: bool = False) -> list[dict]:
    """`n` negative levels on `actor`, each its own effect with a daily save at `dc`
    (none when `permanent` or no DC is known). `once`: energy drain's one save — "a
    success removes that level harmlessly, and a failure makes it permanent" (UMR).
    Records, `_ward_tell`-shaped: what was laid, and death when the levels reach the Hit
    Dice. shortcut: the save falls at the next day boundary the clock crosses, not 24
    hours to the minute; upgrade if a fight ever lasts past midnight."""
    n = max(0, int(n or 0))
    if n <= 0 or actor.is_dead:
        return []
    for _ in range(n):
        periodic = [] if permanent or not dc else [
            {"per": "day", "shed_save": {"save": "fort", "dc": int(dc),
                                         **({"or_permanent": True} if once else {})}}]
        actor.apply_effect(ActiveEffect(
            name=KEY, kind="condition", key=KEY, source=source, origin=origin,
            tags=(TAG,), modifiers=_terms(), periodic=periodic, stacking="stack",
            payload={"dc": dc, "permanent": bool(permanent)}))
        # "reduces its current and total hit points by 5": the total is the effect's
        # term; the current is taken here, once. shortcut: a level shed does not give the
        # 5 current hit points back (they heal as any other), upgrade if the owner rules.
        actor.hp -= 5
    out = [{"kind": "negative_level", "ref": actor.ref, "levels": n, "total": count(actor),
            "dc": dc, "permanent": bool(permanent), "once": bool(once), "source": source,
            "origin": origin}]
    if count(actor) >= max(1, int(actor.hit_dice)):
        if actor.die(f"{source}: negative levels equal to its Hit Dice"):
            out.append({"kind": "condition", "ref": actor.ref, "condition": "dead",
                        "from": "negative levels"})
    else:
        out.extend({"kind": "condition", "ref": actor.ref, "condition": c,
                    "from": "hit points"} for c in actor.apply_hp_state() or ())
    return out


def said(records: list[dict], name: str) -> str:
    """The tell for what `lay` recorded."""
    head = next((r for r in records if r.get("kind") == "negative_level"), None)
    if head is None:
        return ""
    n = head["levels"]
    line = (f"{name} gains {n} negative level{'' if n == 1 else 's'} "
            f"({head['total']} in all): -{head['total']} on attacks, saves, checks and "
            f"caster level, {5 * head['total']} fewer hit points")
    line += "." if head["permanent"] or not head["dc"] else (
        f"; a day on, a Fortitude save (DC {head['dc']}) for each sheds it or makes it "
        f"permanent." if head.get("once") else
        f"; a Fortitude save (DC {head['dc']}) each day may shed one.")
    if any(r.get("condition") == "dead" for r in records):
        line += f" The drain empties {name} of life."
    return line
