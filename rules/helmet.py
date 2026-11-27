"""Wearing a helmet (feat loop b6-rules): the state Dented Helm and Cloven Helm (Dwarves of
Golarion) ask — "When wearing a helmet".

PF1 prints no helmet in the Core armour table (a helm is part of a suit), so the app's
helmets are what its benches and tables already make for the head: a worn record in the
head slot (`tables.SLOTS["head"]` "helms") whose base is a helmet — the leatherworker's cap
(rules/leatherworker.py), a record a bench or a sheet marks `helmet: true` — and the dwarven
boulder helmet, which is a helmet the weapons table carries and is worn to be swung. Asked
as the tag `gear.helmet` (`Actor.standing_tags`), so a feat document's `when.bearer.state`
answers it and taking the cap off takes the tag with it.

shortcut: a plain name typed into the head slot, with no record, is not read — a circlet
and a helm are both strings there; upgrade when the forge makes helms.
"""
from __future__ import annotations

TAG = "gear.helmet"
BASES = ("helm", "helmet", "cap")
BOULDER = "helmet-dwarven-boulder"


def worn(actor) -> dict | None:
    """The helmet this creature wears, or None."""
    for rec in actor.worn_items():
        if str(rec.get("slot") or "").strip().lower() != "head":
            continue
        if rec.get("helmet") or str(rec.get("base") or "").strip().lower() in BASES:
            return rec
    if BOULDER in {str(w).strip().lower() for w in getattr(actor, "weapons", None) or ()}:
        return {"name": "dwarven boulder helmet", "base": "helmet"}
    return None


def tags(actor) -> list[str]:
    return [TAG] if worn(actor) is not None else []
