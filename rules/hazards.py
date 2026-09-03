"""The rule document GM fiat cites: falls, fire, acid, cold, and what they roll.

Stage 8d. Before this, "I jump from the wall" reached the engine as a bare `damage` the
model had written the dice for — a number with nothing behind it, the defect stage 8
exists to close. The brief refused GM fiat as a loophole and named the answer: a rule
document the GM cites. This is that document (content/rules/hazards.json) and its reader.

GAS's SetByCaller, applied to the one op stage 8 invents: the row declares a *slot* — the
one scalar only the fiction can supply (how far the fall, how many rounds in the fire)
with bounds — and the dice per unit of it. The model fills the slot and nothing else; the
engine rolls the row. A slot outside its bounds is refused at validate with the bounds
named, because a 900-foot fall is a number the model wrote, not a fact about a wall.
"""
from __future__ import annotations

import json
from pathlib import Path

_ROWS: dict[str, dict] | None = None


def rows() -> dict[str, dict]:
    global _ROWS
    if _ROWS is None:
        from django.conf import settings

        path = Path(settings.BASE_DIR) / "content" / "rules" / "hazards.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _ROWS = {k: v for k, v in data.items() if not str(k).startswith("_")}
    return _ROWS


def get(rule: str) -> dict | None:
    return rows().get(str(rule or "").strip().lower().replace(" ", "-"))


def names() -> list[str]:
    return sorted(rows())


def check(rule: str, params: dict) -> str:
    """Why this hazard intent cannot run, with the fix named — or ""."""
    row = get(rule)
    if row is None:
        return (f"no hazard rule called {rule!r}. The rules are: {', '.join(names())}. "
                f"A trap is narrated, not rolled, this stage.")
    slot = row["slot"]
    got = params.get(slot["name"])
    if got in (None, ""):
        return (f"{rule} needs {slot['name']} ({slot['min']}–{slot['max']}): the one "
                f"number the scene supplies; the dice are the rule's.")
    try:
        value = int(got)
    except (TypeError, ValueError):
        return f"{rule}: {slot['name']} must be a whole number between {slot['min']} and {slot['max']}."
    if not slot["min"] <= value <= slot["max"]:
        return (f"{rule}: {slot['name']} {value} is outside the rule's {slot['min']}–"
                f"{slot['max']}. Write the number the scene actually has.")
    return ""


def plan(rule: str, params: dict) -> dict:
    """What the row rolls for these slot values: dice, type, lethality, and the slot."""
    row = get(rule)
    slot = row["slot"]
    value = int(params.get(slot["name"]))
    units = max(1, value // int(slot.get("per", 1)))
    per = str(row.get("immersed_dice_per_unit") if params.get("immersed")
              and row.get("immersed_dice_per_unit") else row["dice_per_unit"])
    count, sides = per.lower().split("d")
    dice = f"{int(count) * units}d{int(sides)}"
    out = {"rule": str(rule).strip().lower(), "name": row["name"], "dice": dice,
           "type": str(row.get("type", "untyped")),
           "lethality": str(row.get("lethality", "lethal")),
           "slot": slot["name"], "value": value, "source": row.get("source", "")}
    if row.get("deliberate_first_die_nonlethal") and params.get("deliberate"):
        # A deliberate jump: the first die is nonlethal, the rest is not.
        out["first_die_nonlethal"] = True
        out["first_die"] = f"1d{int(sides)}"
        out["dice"] = f"{int(count) * units - 1}d{int(sides)}" if int(count) * units > 1 else ""
    return out
