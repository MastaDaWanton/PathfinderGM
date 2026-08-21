"""Crafting chains: what a set of ingredients and a sequence of methods produces.

The Herbalist document's own framing — *"crafting is no longer limited to single-step
recipes. Complex items require Crafting Chains—combining multiple methods across
different tools"* — so a craft is an ordered list of methods applied to a set of
ingredients, and the chain is the thing that gets validated, not the recipe.

Two rules here are the author's percentages made precise, because 1e has none and a
percentage without a rounding rule is a bug waiting for a report:

  Costs and penalties round **down**, benefits round **up**. A character is never
  surprised in the direction that hurts them, and `mix` at 80% of a 1d4 is 1d4 rather
  than a silent 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import ingredients as ing_mod
from . import worldclass as wc

# Methods that change what a mixture is worth, as multipliers on its potency. Everything
# else in the method list shapes or enables rather than scaling.
POTENCY = {
    "mix": 0.80,        # "retains the primary effects of both at 80% of base strength"
    "distill": 1.25,    # "increases the strength of a concoction's primary effect by 25%"
    "refine": 1.25,     # "increases the effectiveness of any crafted item to 125%"
}

# Methods that remove an ingredient's drawback rather than scaling it.
CLEANSING = ("purify", "neutralize")

# The method that has to come last if it is used at all: you brew the mixture, you do not
# grind the tea.
FINISHING = ("brew", "catalyst crafting")


class CraftError(ValueError):
    """The chain cannot be attempted. Raised before anything is scored, so a chain the
    character cannot make never advances their track."""


@dataclass
class Chain:
    track: str
    methods: list[str] = field(default_factory=list)
    ingredient_ids: list[str] = field(default_factory=list)
    name: str = ""

    @property
    def stages(self) -> int:
        return len(self.methods)


@dataclass
class Result:
    name: str
    tier: str
    rank: int
    stages: int
    potency: float
    cleansed: bool
    risky: bool
    dc: int
    chance: int
    ingredients: list[dict]
    effects: list[str]
    drawbacks: list[str]
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name, "tier": self.tier, "rank": self.rank,
            "stages": self.stages, "potency": round(self.potency, 2),
            "cleansed": self.cleansed, "risky": self.risky, "dc": self.dc,
            "chance": self.chance, "ingredients": self.ingredients,
            "effects": self.effects, "drawbacks": self.drawbacks,
            "problems": self.problems,
        }


def scale(text: str, potency: float) -> str:
    """Say what a multiplier did, without pretending to rewrite the prose.

    Parsing "+2 alchemical bonus on saves for 8 hours" into a structure and scaling every
    number in it is a much larger job than this page needs, and doing it badly would put
    wrong numbers on screen with an authoritative face. The multiplier is stated instead,
    and the player applies it — which is what a table does anyway.
    """
    if abs(potency - 1.0) < 0.01:
        return text
    return f"{text}  [×{potency:.2f} from the chain]"


def preview(track_id: str, level: int, chain: Chain) -> Result:
    """What this chain would make, and how likely it is to work.

    Never raises for a chain that is merely bad — an empty pot, a method the character
    has not learned, an ingredient beyond their tier all come back as `problems` so the
    page can grey the button and say why. `CraftError` is for chains that cannot be
    described at all.
    """
    track = wc.get(track_id)
    level = max(1, min(int(level), track.max_level))
    known = track.unlocked_methods(level)
    ceiling = wc.tier_rank(track.at(level).max_tier)

    problems: list[str] = []
    items = []
    for iid in chain.ingredient_ids:
        try:
            items.append(ing_mod.get(iid))
        except KeyError:
            problems.append(f"No such ingredient: {iid}.")

    for m in chain.methods:
        if m not in track.unlocked_methods(track.max_level):
            problems.append(f"{track.name} has no method called {m!r}.")
        elif m not in known:
            need = next(l.level for l in sorted(track.levels, key=lambda x: x.level)
                        if m in l.methods)
            problems.append(f"{m.title()} is learned at {track.name} {need}.")

    for i in items:
        if i.rank > ceiling:
            problems.append(f"{i.name} is {i.tier}; {track.name} {level} works "
                            f"{track.at(level).max_tier} at best.")

    if not items:
        problems.append("Nothing in the pot.")
    if not chain.methods:
        problems.append("No method chosen.")

    for m in chain.methods[:-1]:
        if m in FINISHING:
            problems.append(f"{m.title()} finishes a chain; nothing follows it.")

    # The result is as rare as its rarest component, which is also what gates who can
    # make it — a common chain with one legendary petal in it is a legendary brew.
    rank = max((i.rank for i in items), default=1)
    tier = wc.TIERS[rank - 1]

    potency = 1.0
    for m in chain.methods:
        potency *= POTENCY.get(m, 1.0)
    cleansed = any(m in CLEANSING for m in chain.methods)
    risky = any(i.risky for i in items) and not cleansed

    effects = [scale(i.text, potency) for i in items if i.text]
    drawbacks = []
    if risky:
        drawbacks.append("Untreated hazardous components: harvesting and handling risks "
                         "still apply. Purify or Neutralize removes them.")
    if cleansed:
        effects.append("Side effects and secondary toxicities removed by the chain.")

    dc = _dc(items, rank, chain.stages)
    return Result(
        name=chain.name or _name_for(items, chain.methods),
        tier=tier, rank=rank, stages=chain.stages, potency=potency,
        cleansed=cleansed, risky=risky, dc=dc,
        chance=_chance(dc, level, rank, problems),
        ingredients=[i.as_dict() for i in items],
        effects=effects, drawbacks=drawbacks, problems=problems,
    )


def _dc(items, rank: int, stages: int) -> int:
    """Hardest ingredient sets the floor; length of the chain adds to it.

    Ingredients that carry their own DC use it — 31 of them do, and an authored number
    beats a derived one every time. The rest fall back on their tier.
    """
    stated = [i.craft_dc for i in items if i.craft_dc is not None]
    base = max(stated) if stated else 5 + 5 * rank
    return base + 2 * max(0, stages - 1)


def _chance(dc: int, level: int, rank: int, problems: list[str]) -> int:
    """Percent chance the craft succeeds.

    A d20 roll against the chain's DC, with the crafter's level and the gap between their
    tier and the material's standing in for a skill bonus. Clamped to 5-95 rather than
    allowed to reach certainty: a natural 1 fails, so no craft is ever safe, and the
    number on the button should never claim otherwise.
    """
    if problems:
        return 0
    bonus = 3 * level + 2 * max(0, (level - rank))
    need = dc - bonus
    chance = int(round(100 * (21 - need) / 20))
    return max(5, min(95, chance))


def _name_for(items, methods) -> str:
    """A working name, so the preview is not headed "Untitled"."""
    if not items:
        return "Empty pot"
    lead = items[0].name
    shape = {
        "grind": "Powder", "mix": "Compound", "brew": "Tea", "preserve": "Preserve",
        "extract": "Extract", "distill": "Tincture", "purify": "Purified Draught",
        "infuse": "Infusion", "neutralize": "Neutralised Draught", "refine": "Elixir",
        "catalyst crafting": "Catalyst",
    }
    last = methods[-1] if methods else ""
    return f"{lead} {shape.get(last, 'Preparation')}"
