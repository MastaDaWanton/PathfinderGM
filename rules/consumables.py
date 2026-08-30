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
from .tables import SAVES

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


# --- what is harm, and what is a poison -----------------------------------------------------
#
# Measured on the shipped corpus: 99 of the 178 effects the 161 ingredients carry are harm,
# and every one of them was printed under "Effects" beside the bonuses. The Drawbacks
# section said one boilerplate sentence that named nothing.


def _branches(spec: dict) -> list[dict]:
    return list(spec.get("on_failure") or []) + list(spec.get("on_success") or [])


def _poisonous(spec: dict) -> bool:
    """Harm that makes the thing a poison: what `HARMFUL` names, minus the bare gate.

    The gate is excluded because a save on its own poisons nobody. It is the *body* of a
    poison that decides there is one, and the save is then attached to it.
    """
    kind = str(spec.get("type", ""))
    return kind in HARMFUL and kind != "save_gate"


def hurts(spec: dict) -> bool:
    """Whether one effect is harm — the question the Drawbacks section asks.

    Wider than `HARMFUL` by exactly one case, and the difference is deliberate. A -2
    penalty is harm on a card, but it is not a poison: it does not make a draught worth
    throwing at anybody or worth putting on a blade, which is the only question `HARMFUL`
    is asked. 20 of the corpus's 178 effects are penalties, and "-2 to all actions while
    in the area" sitting under Effects next to "+5 save vs poison" is what this separates.

    A bare `save_gate` is *not* harm on its own. 41 of the corpus's 59 gates carry nothing
    at all — they are the entry's own crafting DC, restated at the end of the description
    ("Cave Star ... DC: 10.") and swept up by the extractor's bare-DC fallback. Filing
    those under Drawbacks would have invented 41 poisons that poison nobody. A gate earns
    its place by gating something, either in its own branches or through the source it
    came in with, which `poisons` below works out.
    """
    kind = str(spec.get("type", ""))
    if kind == "save_gate":
        return any(hurts(x) for x in _branches(spec))
    if kind in HARMFUL:
        return True
    if kind.endswith("_mod"):
        try:
            return int(spec.get("amount", 0)) < 0
        except (TypeError, ValueError):
            return False
    return False


def _lower_first(s: str) -> str:
    """"Causes nauseated" reads as a clause, not a sentence, once it is joined to a save.

    Left alone when the second character is also upper case, so "DR 3/—" does not come
    back as "dR 3/—".
    """
    return s[0].lower() + s[1:] if len(s) > 1 and not s[1].isupper() else s


@dataclass
class Poison:
    """One source's harmful cluster: the save that gates it, what it does, and where it
    came from.

    Grouped rather than listed flat because the extractor finds a poison in pieces. Dragon
    Flower's card read "1d6 Constitution damage", "Fortitude DC 25" and "Causes nauseated"
    as three unrelated lines, and the save that gates the damage looked like an effect of
    its own. 1e writes a poison as one thing: a save, and what happens when you fail it.

    The source is the ingredient's own name rather than an invented one. A generated name
    would be a fact nobody wrote, and "Dragon Flower" is the name the player picked off the
    shelf.
    """
    source: str = ""
    # The gate spec itself, kept rather than only its numbers, so whatever consumes this
    # can tell that the gate has been accounted for and must not be listed again.
    gate: dict | None = None
    effects: list[dict] = field(default_factory=list)

    @property
    def dc(self) -> int | None:
        if not self.gate or self.gate.get("dc") in (None, ""):
            return None
        try:
            return int(self.gate["dc"])
        except (TypeError, ValueError):
            return None

    @property
    def save(self) -> str:
        """"fort", "ref", "will" — or empty, which 55 of the 59 gates in the corpus are.

        The source states a bare DC and never says which save; choosing one would put a
        fact on the card that nobody wrote.
        """
        return str((self.gate or {}).get("target") or "").lower()

    @property
    def save_line(self) -> str:
        dc = self.dc
        if dc is None:
            return ""
        return f"{SAVES.get(self.save, '')} DC {dc}".strip()

    @property
    def lines(self) -> list[str]:
        return [effectspec.render(s) for s in self.effects]

    @property
    def harm(self) -> str:
        """What failing the save costs, as one clause.

        Composed here rather than in the template so the rule for joining them lives in
        one language. A page that rebuilt this line in JavaScript would be the second copy
        that goes stale.
        """
        return ", ".join(_lower_first(line) for line in self.lines)

    @property
    def body(self) -> str:
        """The save and what failing it costs, without the source's name in front."""
        gate = self.save_line
        return f"{gate} or {self.harm}" if gate else self.harm

    @property
    def line(self) -> str:
        """The card line. Keeps the "Source: mechanic" shape the effect list already uses,
        so the two panels read the same way and the page can dim the source on both."""
        return f"{self.source}: {self.body}" if self.source else self.body

    def as_dict(self) -> dict:
        return {"source": self.source, "save": self.save, "dc": self.dc,
                "save_line": self.save_line, "lines": self.lines, "harm": self.harm,
                "body": self.body, "line": self.line}


@dataclass
class Sorted:
    """A list of effects, sorted into what it does for you and what it does to you.

    `benefits` holds the same dict objects that were passed in, not copies, so a caller
    holding a line beside each spec can match them back by identity.
    """
    benefits: list[dict] = field(default_factory=list)
    poisons: list[Poison] = field(default_factory=list)
    penalties: list[dict] = field(default_factory=list)


def poisons(specs: list[dict], source: str = "") -> list[Poison]:
    """Every harmful cluster in a list of effects, one poison per source that carries harm.

    Grouped by `from` — the ingredient each effect was read out of — because that is the
    only thing tying a save to the damage it gates. Taking "the first save in the list"
    instead worked for a one-ingredient item and quietly dropped the second poison's save
    from anything made of two.
    """
    order: list[str] = []
    groups: dict[str, list[dict]] = {}
    for spec in specs:
        key = str(spec.get("from") or source)
        if key not in groups:
            order.append(key)
            groups[key] = []
        groups[key].append(spec)

    out: list[Poison] = []
    for key in order:
        group = groups[key]
        gates = [s for s in group if str(s.get("type")) == "save_gate"]
        # An authored gate carries its own branches and is a whole poison by itself. The
        # extractor never nests, so its gates arrive bare and belong to whatever else
        # their source brought in with them.
        for gate in gates:
            branch = [x for x in _branches(gate) if _poisonous(x)]
            if branch:
                out.append(Poison(source=key, gate=gate, effects=branch))
        body = [s for s in group if _poisonous(s)]
        if body:
            bare = next((g for g in gates if not _branches(g)), None)
            out.append(Poison(source=key, gate=bare, effects=body))
    return out


def sort_harm(specs: list[dict], source: str = "") -> Sorted:
    """Split a list of effects into benefits, poisons and loose penalties."""
    found = poisons(specs, source)
    claimed = [s for p in found for s in p.effects]
    claimed += [p.gate for p in found if p.gate is not None]
    pen = [s for s in specs
           if not any(s is c for c in claimed) and hurts(s) and not _poisonous(s)]
    claimed += pen
    return Sorted(benefits=[s for s in specs if not any(s is c for c in claimed)],
                  poisons=found, penalties=pen)


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
    text = str(dice or "")
    # The corpus's range form, normalised to real dice before anything else: "1-4" is
    # 1d4 and "2-8" is 1d7+1. Left alone, a range fell through the notation match and
    # potency silently never applied — a 506% Comfrey Tea healed exactly what a plain
    # one did, which is the player's brewing thrown away without a word.
    r = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", text)
    if r and int(r.group(2)) > int(r.group(1)):
        lo, hi = int(r.group(1)), int(r.group(2))
        flat0 = lo - 1
        text = f"1d{hi - lo + 1}" + (f"+{flat0}" if flat0 else "")
    m = _DICE.match(text)
    if not m or abs(potency - 1.0) < 0.01:
        return text
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

    if kind in ("save_mod", "skill_mod", "ability_mod", "combat_mod"):
        amount = int(spec.get("amount", 0) or 0)
        # Potency scales benefits the way it scales dice — the author's distill rule is
        # about the primary effect, not only the numbered ones — and rounds up, per the
        # house rounding. Penalties are left alone: a stronger brew is not a worse one.
        if amount > 0 and potency > 1.0:
            amount = int(amount * potency + 0.999)
        out = [{"op": "buff", "actor": target, "because": because,
                "params": {"type": kind, "target": spec.get("target", ""),
                           "amount": amount, "to": target,
                           "source": spec.get("from") or "the preparation",
                           # The channel the author already filled in. Dropped here
                           # for the life of the feature, so every brew stacked with
                           # every other brew of its own kind.
                           **({"bonus_type": spec["bonus_type"]}
                              if spec.get("bonus_type") else {}),
                           **({"duration": spec["duration"]}
                              if isinstance(spec.get("duration"), dict) else
                              {"duration": {"amount": 1, "unit": "hour"}}),
                           **({"note": spec["note"]} if spec.get("note") else {})}}]
        return out

    if kind == "remove_condition":
        return [{"op": "condition", "because": because,
                 "params": {"condition": spec.get("target") or "", "to": target,
                            "remove": True}}]

    return []


def _gate_intent(poison: Poison, target: str, because: str) -> list[dict]:
    """A poison's saving throw, emitted once before what it does.

    The extractor produces `save_gate` as its own effect — "Fortitude DC 25" sits beside
    "1d6 Constitution damage" rather than wrapping it — so the two are stitched back
    together by `poisons()`. Without this the save is a line on a card that nothing ever
    rolls.

    Falls back to Fortitude when the source names a DC and no save, which is 55 of the
    corpus's 59 gates. Poison is a Fortitude affair in 1e, and rolling the wrong save is
    still better than the alternative here: not rolling at all.
    """
    dc = poison.dc
    if dc is None:
        return []
    return [{"op": "save", "actor": target, "because": because,
             "params": {"save": poison.save or "fort", "dc": {"value": dc}},
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
    # Throwing needs something to hurt whoever it lands on. Painting a blade does not:
    # a weapon oil that sharpens the edge or makes it count as magic is the whole
    # point of oils, and gating `coat` on harm refused four of the alchemist's own
    # recipes — oil of magic weapon, magic fang, align weapon and keen edge — with
    # "does nothing harmful, so there is nothing to put on a blade". A benign coating
    # is declared by its maker (`how` says coat) and buffs the wielder rather than
    # poisoning the target.
    declared = [str(x).lower() for x in (_field(stock, "how", []) or [])]
    benign_coat = how == "coat" and "coat" in declared
    if how == "throw" and not is_harmful(stock):
        use.problems.append(
            f"{name} does nothing harmful, so there is nothing to throw at anybody")
        return use
    if how == "coat" and not is_harmful(stock) and not benign_coat:
        use.problems.append(
            f"{name} does nothing harmful, so there is nothing to put on a blade")
        return use
    if not _field(stock, "count", 1):
        use.problems.append(f"no {name} left")
        return use

    why = because or f"{name}, {how}"
    if benign_coat:
        # The oil is on your own weapon, so its bonuses are yours. Aimed at the wielder
        # rather than the target — the opposite of a poison, and the reason `coat` could
        # not simply be let through unchanged.
        target = "pc"
    # Each poison's own save, rolled before the harm it gates. Grouped rather than "the
    # first gate in the list", so a compound made of two poisonous ingredients rolls both
    # saves; before, the second one's save was never rolled at all.
    found = poisons(specs, source=str(name))
    claimed = [s for p in found for s in p.effects] + [p.gate for p in found if p.gate]
    for poison in found:
        use.intents.extend(_gate_intent(poison, target, why))
        for spec in poison.effects:
            _resolve(spec, target, potency, why, use)
    for spec in specs:
        if str(spec.get("type")) == "save_gate" or any(spec is c for c in claimed):
            continue
        _resolve(spec, target, potency, why, use)
    return use


def _resolve(spec: dict, target: str, potency: float, because: str, use: Use) -> None:
    """One effect into the outcome: as intents if the engine can run it, as a line for the
    GM if it cannot. Never silently nothing — an item that quietly does less than its card
    says is worse than one that says "and the rest is up to you"."""
    if not effectspec.executable(spec):
        use.narrate.append(effectspec.render(spec))
        return
    made = _spec_to_intents(spec, target, potency, because)
    if made:
        use.intents.extend(made)
    else:
        # Executable in principle, no mapping here yet. Still the GM's to narrate.
        use.narrate.append(effectspec.render(spec))


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
    """What a coated blade delivers when it lands.

    Poison by poison, so a blade painted with a two-ingredient brew rolls a save for each
    of them rather than for whichever one the extractor happened to list first.
    """
    why = f"{coating.item} on the blade"
    found = poisons(coating.specs, source=coating.item)
    claimed = [s for p in found for s in p.effects] + [p.gate for p in found if p.gate]
    out: list[dict] = []
    for poison in found:
        out.extend(_gate_intent(poison, target, why))
        for spec in poison.effects:
            if effectspec.executable(spec):
                out.extend(_spec_to_intents(spec, target, coating.potency, why))
    for spec in coating.specs:
        if str(spec.get("type")) == "save_gate" or any(spec is c for c in claimed):
            continue
        if effectspec.executable(spec):
            out.extend(_spec_to_intents(spec, target, coating.potency, why))
    return out


__all__ = ["Coating", "HARMFUL", "Poison", "SPLASH_RADIUS_FT", "Sorted", "Use",
           "coating_from_dict", "coating_intents", "hurts", "is_harmful", "plan",
           "poisons", "scale", "sort_harm"]
