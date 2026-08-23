"""Pools a character spends: ki, rage rounds, uses per day, stacks on an enemy.

Blood Bending is the reason this exists, and it forced three things a first sketch of the
model did not have. Each is written up in `docs/homebrew-rules.md` §4.2, and each came from
an ability that would otherwise have been unimplementable:

- **`scope: target`.** A resource does not always belong to whoever made it. Blood stacks
  live on the *enemy*, are applied by one ability and spent by four others, and the owner
  never holds them.
- **Dice cooldowns.** Vampiric Recovery recharges on 1d3 turns, not on an integer.
- **Upkeep.** A bloodlink costs 1d10 non-lethal every round or it drops. Nothing else in
  the app charges rent.

A pool is data, not code. Its maximum is a formula over sheet values — `floor(level/2) +
con_mod` — evaluated by a restricted parser rather than `eval`, because a formula arrives
from a homebrew file and a file is not a trusted thing to execute.
"""
from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass, field

from .tables import ABILITIES, ability_modifier

# --- formulas -------------------------------------------------------------------------------
#
# `floor(level/2) + con_mod`. Parsed to an AST and walked with an explicit whitelist: a
# homebrew file is not a trusted thing to execute, and `eval` on one is how a content pack
# becomes a shell.

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}

_FUNCS = {
    "floor": lambda x: int(x // 1),
    "ceil": lambda x: -int((-x) // 1),
    "min": min,
    "max": max,
    "round": round,
}


class FormulaError(ValueError):
    """The formula names something that does not exist, or does something it may not."""


def variables(actor) -> dict[str, int]:
    """Everything a formula may refer to, read off the sheet.

    Named explicitly rather than exposing the Actor: a formula should be able to say
    `con_mod` and should not be able to say `actor.__class__`.
    """
    out = {
        "level": actor.level,
        "hit_dice": actor.hit_dice,
        "hp": actor.hp,
        "hp_max": actor.hp_max,
        "temp_hp": actor.temp_hp,
        "bab": actor.bab,
    }
    # A branching class tiers its abilities against its own track rather than against
    # character level, so a formula has to be able to say so. Zero for every class that
    # does not branch, which is every class but one.
    from . import leveling

    tracks = leveling.control_blood(actor)
    out["control_blood"] = max(tracks.values())
    out["control_blood_a"], out["control_blood_b"] = tracks["a"], tracks["b"]
    for ab in ABILITIES:
        out[ab] = actor.ability_score(ab)
        out[f"{ab}_mod"] = actor.ability_mod(ab)
    return out


def evaluate(formula, actor) -> int:
    """A formula over sheet values, as an integer.

    Rounded down at the end, once — 1e rounds fractions down unless it says otherwise, and
    rounding at each step compounds differently depending on how the formula was written.
    """
    if isinstance(formula, (int, float)):
        return int(formula)
    text = str(formula).strip()
    if not text:
        return 0
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"{text!r} is not a formula: {exc.msg}") from exc
    value = _walk(tree.body, variables(actor), text)
    return int(value // 1)


def _walk(node, names: dict[str, int], text: str):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise FormulaError(f"{text!r}: only numbers may be written literally")
    if isinstance(node, ast.Name):
        if node.id not in names:
            close = ", ".join(sorted(names)[:8])
            raise FormulaError(f"{text!r}: nothing called {node.id!r}. Available: {close}…")
        return names[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_walk(node.left, names, text),
                                   _walk(node.right, names, text))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_walk(node.operand, names, text))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in _FUNCS:
        return _FUNCS[node.func.id](*[_walk(a, names, text) for a in node.args])
    raise FormulaError(f"{text!r}: {type(node).__name__} is not allowed in a formula")


def check(formula) -> str:
    """Validate a formula without an actor, for the editor. Returns a problem or ""."""
    class _Probe:
        level = hit_dice = hp = hp_max = temp_hp = bab = 1

        def ability_score(self, _):
            return 10

        def ability_mod(self, _):
            return 0

    try:
        evaluate(formula, _Probe())
    except FormulaError as exc:
        return str(exc)
    return ""


# --- pools ----------------------------------------------------------------------------------

# What a spent pool waits on before it refills.
REFRESH = ("rest.night", "rest.any", "encounter.end", "round.start", "never")


@dataclass
class Pool:
    """One resource on one character."""
    id: str
    current: int = 0
    maximum: int = 0
    # The formula the maximum came from, kept so a level-up recomputes rather than
    # freezing the number the character had when the pool was created.
    max_formula: str = ""
    refresh: str = "rest.night"
    # `self` or `target`: a blood stack sits on the creature it was applied to.
    scope: str = "self"
    # None means uncapped, which two Blood Bending paths declare in as many words.
    capped: bool = True
    # Rounds remaining before this can be used again. Rolled, not fixed: 1d3 turns.
    cooldown_left: int = 0
    cooldown_dice: str = ""
    # Paid every round or the thing it sustains ends.
    upkeep_amount: str = ""
    upkeep_resource: str = ""
    source: str = ""

    @property
    def ready(self) -> bool:
        return self.cooldown_left <= 0

    def as_dict(self) -> dict:
        return {
            "id": self.id, "current": self.current, "maximum": self.maximum,
            "max_formula": self.max_formula, "refresh": self.refresh,
            "scope": self.scope, "capped": self.capped,
            "cooldown_left": self.cooldown_left, "cooldown_dice": self.cooldown_dice,
            "upkeep_amount": self.upkeep_amount, "upkeep_resource": self.upkeep_resource,
            "source": self.source, "ready": self.ready,
        }


def from_dict(d: dict) -> Pool:
    return Pool(
        id=d["id"], current=int(d.get("current", 0)),
        maximum=int(d.get("maximum", 0)), max_formula=str(d.get("max_formula", "")),
        refresh=d.get("refresh", "rest.night"), scope=d.get("scope", "self"),
        capped=bool(d.get("capped", True)),
        cooldown_left=int(d.get("cooldown_left", 0)),
        cooldown_dice=d.get("cooldown_dice", ""),
        upkeep_amount=d.get("upkeep_amount", ""),
        upkeep_resource=d.get("upkeep_resource", ""),
        source=d.get("source", ""),
    )


def define(actor, spec: dict) -> Pool:
    """Create or recompute a pool on an actor from its definition.

    Recompute rather than create-once: a maximum written as a formula must follow a level
    up, and a pool frozen at the value it had when the character was 1st level is a bug
    that only shows itself several sessions later.
    """
    pid = str(spec["id"]).strip().lower()
    maximum = evaluate(spec.get("max", 0), actor) if spec.get("max") not in (None, "") else 0
    pool = actor.pools.get(pid)
    if pool is None:
        pool = Pool(id=pid)
        actor.pools[pid] = pool
        starts = spec.get("starts", "max")
        pool.current = maximum if starts == "max" else int(starts or 0)

    pool.max_formula = str(spec.get("max", "") or "")
    pool.maximum = maximum
    pool.refresh = spec.get("refresh", pool.refresh)
    pool.scope = spec.get("scope", pool.scope)
    pool.capped = bool(spec.get("capped", spec.get("cap", "yes") != "none"))
    pool.cooldown_dice = str(spec.get("cooldown", "") or "")
    upkeep = spec.get("upkeep") or {}
    pool.upkeep_amount = str(upkeep.get("amount", "") or "")
    pool.upkeep_resource = str(upkeep.get("resource", "") or "")
    pool.source = spec.get("source", pool.source)
    if pool.capped:
        pool.current = min(pool.current, pool.maximum)
    return pool
