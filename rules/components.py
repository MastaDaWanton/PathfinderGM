"""Costly material components (CRB, Magic, "Components"; aonprd.com/Rules.aspx?ID=213, read
2026-11-26): "Material (M): A material component consists of one or more physical
substances or objects that are annihilated by the spell energies in the casting process.
Unless a cost is given for a material component, the cost is negligible ... assume you have
all you need as long as you have your spell component pouch." "Focus (F): A focus component
is a prop of some sort. Unlike a material component, a focus is not consumed when the spell
is cast and can be reused." And Eschew Materials (CRB): "If the spell requires a material
component that costs more than 1 gp, you must have the material component on hand to cast
the spell, as normal."

Measured before (feat loop b4-moves' Eschew Materials): `Spell.component_cost` was kept and
read by nothing, so stoneskin's 250 gp of diamond dust and raise dead's 5,000 gp diamond
were free, cast after cast.

Only the costly ones are tracked — the owner's instruction for this lane: "don't make
players track bat guano". So a component of 1 gp or less is never asked (the pouch, and
Eschew Materials, cover it), and the feat is the book's whole effect here.

The material is one carried good, `costly spell components`, counted in gold pieces of
value (content/rules/gear.json; rules/goods.py GEAR): bought at a general counter, spent by
the casting — the shape the services already price a temple's casting by (rules/services.py:
"(spell id, costly material in gp)"). Owner call: one generic stock rather than diamond
dust, onyx and incense by name — no table here names the substances, and matching a
player's "diamond" against a spell's text is reading English.

A focus with a cost (F) must be on hand and is not spent. Asked of the player always; of a
creature only once it carries the good, as arrows are (`Engine._op_attack`'s ammunition):
a stat block's caster is written with its components assumed.
"""
from __future__ import annotations

import math

GOOD = "costly spell components"


def cost(spell) -> float:
    """The spell's component cost in gp, 0 when none or unreadable ("50 / 100" is two
    versions' costs, and which applies is the spell text's; the higher is asked)."""
    raw = str(getattr(spell, "component_cost", "") or "").strip()
    if not raw:
        return 0.0
    vals = []
    for part in raw.split("/"):
        try:
            vals.append(float(part.strip()))
        except ValueError:
            continue
    return max(vals) if vals else 0.0


def kind(spell) -> str:
    """"M" when the costly part is a material (consumed), "F" a focus (kept), else ""."""
    comps = {str(c).strip().upper() for c in getattr(spell, "components", None) or ()}
    if cost(spell) <= 1:
        return ""
    if "M" in comps:
        return "M"
    if "F" in comps:
        return "F"
    return ""


def carried(actor) -> int:
    from . import gear

    return sum(int(c["count"]) for c in gear.carried(actor) if c["key"] == GOOD)


def asked_of(actor) -> bool:
    return bool(actor.is_pc) or carried(actor) > 0


def refusal(actor, spell) -> str:
    """Why this caster cannot cast it for want of the component, or ""."""
    need = math.ceil(cost(spell)) if kind(spell) else 0
    if not need or not asked_of(actor) or carried(actor) >= need:
        return ""
    what = "focus" if kind(spell) == "F" else "material component"
    return (f"{spell.name} needs a costly {what} worth {need} gp on hand, and "
            f"{actor.name} carries {carried(actor)} gp of costly spell components. Nothing "
            f"is cast.")


def spend(actor, spell) -> dict | None:
    """The material annihilated by the casting: its gp of the good taken, and the record."""
    from . import gear

    need = math.ceil(cost(spell)) if kind(spell) == "M" else 0
    if not need or not asked_of(actor):
        return None
    left = need
    for c in gear.carried(actor):
        if c["key"] != GOOD or left <= 0:
            continue
        n = min(left, int(c["count"]))
        gear.spend(actor, c, n)
        left -= n
    return {"ref": actor.ref, "kind": "component_spent", "spell": spell.id, "gp": need,
            "origin": "rule:material-component"}
