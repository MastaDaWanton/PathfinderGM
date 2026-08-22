"""Drinking it, throwing it, and putting it on a blade.

A crafted potion used to be a paragraph. It had a name, a rarity, a potency multiplier and
a list of effects written for a person to read, and nothing in the engine could do anything
with any of it — the player threw a tincture at a beast and got narration, because
narration was the only thing available.

`Stock.specs` closed half of that: the same effects the card shows, in the structured form
`rules/effectspec.py` defines. This closes the other half, by turning those specs into
intents the engine already knows how to resolve. Nothing new is invented — a potion that
heals emits the `heal` op, one that poisons emits `save` and `ability_damage`, and both go
through the same validation as anything the GM proposes.

**Three ways to use one, and the difference is real.**

  drink   the whole dose, on yourself or somebody you can touch
  throw   a splash weapon: a ranged touch attack, and 1e's splash rules
  coat    a blade, if the thing is harmful — it waits on the weapon for the next hit

**Potency is applied here and nowhere else.** A chain's multiplier is a property of the
result, stated once on the card beside the rarity; stamping it onto every effect line was
noise on every card in the app. But it has to reach the dice eventually, and this is the
only place that rolls them.

**What it will not do.** A spec `effectspec.executable()` says the engine cannot resolve is
carried into the outcome as text for the GM to narrate, never silently dropped and never
guessed at. An item whose every effect is prose is still a usable item; it just does what
the fiction says rather than what the engine does.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import effectspec

# Effects that hurt whoever receives them. A thing made of these is a poison: it is worth
# throwing, and it is worth putting on a blade. Anything else is a draught.
HARMFUL = {"damage", "ability_damage", "ability_drain", "bleed", "apply_condition",
           "save_gate"}

# What a splash weapon does to everyone around the square it lands in. 1e: "splash weapons
# deal 1 point of splash damage to all creatures within 5 feet of the target".
SPLASH_RADIUS_FT = 5

_DICE = re.compile(r"^\s*(\d+)d(\d+)\s*(?:([+-])\s*(\d+))?\s*$", re.I)


@dataclass
class Use:
    """One consumable being used, resolved into things the engine can do."""
    item: str
    how: str                      # drink | throw | coat
    intents: list[dict] = field(default_factory=list)
    # Effects the engine cannot resolve, kept verbatim for the GM to narrate. Never
    # dropped: an item that quietly does less than its card says is worse than one that
    # says "and the rest is up to you".
    narrate: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def is_harmful(stock) -> bool:
    """Would this hurt whoever got it? Decides what may be thrown and what may coat a
    blade, and it is read off the effects rather than the name — "Purified Draught of
    Skull Orchid" is not made safe by being called one."""
    return any(str(s.get("type")) in HARMFUL for s in _specs(stock))


def _specs(stock) -> list[dict]:
    if isinstance(stock, dict):
        return [dict(s) for s in (stock.get("specs") or [])]
    return [dict(s) for s in (getattr(stock, "specs", None) or [])]


def _field(stock, name, default=None):
    if isinstance(stock, dict):
        return stock.get(name, default)
    return getattr(stock, name, default)


def scale(dice: str, potency: float) -> str:
    """Apply a chain's potency to a dice expression.

    Scales the flat part rather than the number of dice, because "1d6 at 125%" as 1.25d6
    is not a thing anyone can roll. 1d6 at 125% becomes 1d6+2: a quarter of the average
    (3.5), rounded the way `crafting` rounds — benefits up, and this is only ever called
    on the thing the player made on purpose.
    """
    m = _DICE.match(str(dice or ""))
    if not m or abs(potency - 1.0) < 0.01:
        return str(dice or "")
    count, sides = int(m.group(1)), int(m.group(2))
    flat = int(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)
    average = count * (sides + 1) / 2
    extra = average * (potency - 1.0)
    flat += int(extra + 0.999) if extra > 0 else int(extra)
    if flat > 0:
        return f"{count}d{sides}+{flat}"
    if flat < 0:
        return f"{count}d{sides}{flat}"
    return f"{count}d{sides}"


def _spec_to_intents(spec: dict, target: str, potency: float, because: str) -> list[dict]:
    """One structured effect as engine intents, or [] if the engine cannot run it."""
    kind = str(spec.get("type", ""))
    dice = spec.get("dice") or spec.get("amount")

    if kind == "heal":
        return [{"op": "heal", "actor": target, "because": because,
                 "params": {"amount": scale(str(dice), potency)}}]

    if kind == "temp_hp":
        return [{"op": "temp_hp", "actor": target, "because": because,
                 "params": {"amount": scale(str(dice), potency),
                            "source": spec.get("from") or "the draught"}}]

    if kind == "damage":
        return [{"op": "damage", "actor": target, "because": because,
                 "params": {"to": target, "amount": scale(str(dice), potency),
                            "type": spec.get("damage_type") or "untyped"}}]

    if kind in ("ability_damage", "ability_drain"):
        return [{"op": "ability_damage", "actor": target, "because": because,
                 "params": {"to": target, "ability": spec.get("target") or "con",
                            "amount": scale(str(dice), potency),
                            "drain": kind == "ability_drain"}}]

    if kind == "apply_condition":
        params = {"condition": spec.get("target") or spec.get("condition") or "sickened",
                  "to": target}
        duration = spec.get("duration")
        if isinstance(duration, dict) and duration.get("amount"):
            params["duration"] = {"amount": duration.get("amount"),
                                  "unit": duration.get("unit", "round")}
        return [{"op": "condition", "because": because, "params": params}]

    if kind == "remove_condition":
        return [{"op": "condition", "because": because,
                 "params": {"condition": spec.get("target") or "", "to": target,
                            "remove": True}}]

    return []


def _save_gate(specs: list[dict], target: str, because: str) -> list[dict]:
    """A poison's saving throw, emitted once before what it does.

    The extractor produces `save_gate` as its own effect — "Fortitude DC 25" sits beside
    "1d6 Constitution damage" rather than wrapping it — so the two are stitched back
    together here. Without this the save is a line on a card that nothing ever rolls.
    """
    gate = next((s for s in specs if str(s.get("type")) == "save_gate"), None)
    if not gate:
        return []
    return [{"op": "save", "actor": target, "because": because,
             "params": {"save": str(gate.get("target") or "fort").lower(),
                        "dc": {"value": int(gate.get("dc") or 10)}},
             "visibility": "player"}]


def plan(stock, how: str = "drink", target: str = "pc",
         because: str = "") -> Use:
    """What using this item actually does, as intents the engine can validate."""
    how = (how or "drink").strip().lower()
    name = _field(stock, "name") or _field(stock, "base") or "the preparation"
    potency = float(_field(stock, "potency", 1.0) or 1.0)
    specs = _specs(stock)
    use = Use(item=str(name), how=how)

    if how not in ("drink", "throw", "coat"):
        use.problems.append(f"{how!r} is not a way to use something; "
                            f"drink, throw or coat")
        return use
    if how in ("throw", "coat") and not is_harmful(stock):
        use.problems.append(
            f"{name} does nothing harmful, so there is nothing to "
            + ("throw at anybody" if how == "throw" else "put on a blade"))
        return use
    if not _field(stock, "count", 1):
        use.problems.append(f"no {name} left")
        return use

    why = because or f"{name}, {how}"
    use.intents.extend(_save_gate(specs, target, why))
    for spec in specs:
        if str(spec.get("type")) == "save_gate":
            continue
        if not effectspec.executable(spec):
            use.narrate.append(effectspec.render(spec))
            continue
        made = _spec_to_intents(spec, target, potency, why)
        if made:
            use.intents.extend(made)
        else:
            # Executable in principle, no mapping here yet. Still the GM's to narrate
            # rather than silently nothing.
            use.narrate.append(effectspec.render(spec))
    return use


@dataclass
class Coating:
    """A harmful preparation waiting on a weapon.

    One hit, then it is gone — 1e poisons are a dose, not an enchantment. Held on the
    actor rather than on the weapon entry because `Actor.weapons` is a list of plain
    strings, and the alternative was giving every torch and rope a coating field.
    """
    item: str
    weapon: str = ""
    specs: list[dict] = field(default_factory=list)
    potency: float = 1.0
    uses_left: int = 1

    def as_dict(self) -> dict:
        return {"item": self.item, "weapon": self.weapon, "specs": self.specs,
                "potency": self.potency, "uses_left": self.uses_left}


def coating_from_dict(d: dict) -> Coating:
    return Coating(
        item=str(d.get("item", "")), weapon=str(d.get("weapon", "")),
        specs=[dict(s) for s in (d.get("specs") or [])],
        potency=float(d.get("potency", 1.0) or 1.0),
        uses_left=int(d.get("uses_left", 1) or 0),
    )


def coating_intents(coating: Coating, target: str) -> list[dict]:
    """What a coated blade delivers when it lands."""
    why = f"{coating.item} on the blade"
    out = _save_gate(coating.specs, target, why)
    for spec in coating.specs:
        if str(spec.get("type")) == "save_gate" or not effectspec.executable(spec):
            continue
        out.extend(_spec_to_intents(spec, target, coating.potency, why))
    return out


__all__ = ["Coating", "HARMFUL", "SPLASH_RADIUS_FT", "Use", "coating_from_dict",
           "coating_intents", "is_harmful", "plan", "scale"]
