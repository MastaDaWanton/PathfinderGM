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

from . import consumables as con
from . import effectspec
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


# --- concentration ------------------------------------------------------------------------
#
# Two doses of a thing make one dose of twice the thing. It is a trade of quantity for
# density rather than a gain: nothing is created, and the pair is spent.
#
# "Tier" in the request is *concentration* here, because `tier` already means rarity
# throughout the engine and a second meaning for the same word would have been a bug
# waiting to happen in every comparison.
CONCENTRATE_COST = 2        # doses in, one out
CONCENTRATE_POTENCY = 2.0   # per step
# Each step also moves the result one band rarer, which gates the ladder on its own:
# Tier 3 is rare material, and working rare material is Herbalist 3.
CONCENTRATE_RARITY_STEP = 1


class CraftError(ValueError):
    """The chain cannot be attempted. Raised before anything is scored, so a chain the
    character cannot make never advances their track."""


@dataclass
class Stock:
    """A crafted item a character is carrying, and can craft with again.

    Held per base name and concentration rather than as a list of individual doses:
    three identical teas are a count of three, not three objects, and the crafting page
    only ever asks "how many of these do I have".
    """
    base: str
    concentration: int = 1
    tier: str = "common"
    potency: float = 1.0
    count: int = 1
    craft: str = "herbalism"
    effects: list[str] = field(default_factory=list)
    drawbacks: list[str] = field(default_factory=list)
    from_ingredients: list[str] = field(default_factory=list)
    # The same effects as `effects`, in the structured form `rules/effectspec.py`
    # defines. `effects` is what a card shows; this is what the engine can actually run.
    # Without it a crafted potion is a paragraph, and drinking one could only ever be
    # narration — which is exactly what it was.
    specs: list[dict] = field(default_factory=list)

    @property
    def id(self) -> str:
        slug = "".join(c if c.isalnum() else "-" for c in self.base.lower()).strip("-")
        while "--" in slug:
            slug = slug.replace("--", "-")
        return f"{slug}#{self.concentration}"

    @property
    def name(self) -> str:
        return self.base if self.concentration <= 1 \
            else f"{self.base} (Tier {self.concentration})"

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "base": self.base,
            "concentration": self.concentration, "tier": self.tier, "rank": self.rank,
            "potency": round(self.potency, 2), "count": self.count, "craft": self.craft,
            "effects": self.effects, "drawbacks": self.drawbacks,
            "specs": self.specs, "from_ingredients": self.from_ingredients,
            "kind": "crafted", "crafted": True,
        }


def from_stock_dict(d: dict) -> Stock:
    return Stock(
        base=d.get("base", d.get("name", "Preparation")),
        concentration=int(d.get("concentration", 1)),
        tier=d.get("tier", "common"), potency=float(d.get("potency", 1.0)),
        count=int(d.get("count", 1)), craft=d.get("craft", "herbalism"),
        effects=list(d.get("effects", [])), drawbacks=list(d.get("drawbacks", [])),
        specs=[dict(x) for x in (d.get("specs") or [])],
        from_ingredients=list(d.get("from_ingredients", [])),
    )


def concentrate(item: Stock) -> Stock:
    """What `CONCENTRATE_COST` of this makes."""
    rank = min(len(wc.TIERS), item.rank + CONCENTRATE_RARITY_STEP)
    return Stock(
        base=item.base, concentration=item.concentration + 1,
        tier=wc.TIERS[rank - 1],
        potency=item.potency * CONCENTRATE_POTENCY,
        count=1, craft=item.craft,
        effects=list(item.effects), drawbacks=list(item.drawbacks),
        specs=[dict(x) for x in item.specs],
        from_ingredients=list(item.from_ingredients),
    )


@dataclass
class Chain:
    track: str
    methods: list[str] = field(default_factory=list)
    ingredient_ids: list[str] = field(default_factory=list)
    name: str = ""
    # Crafted items going back into the pot, as {stock id: how many}. Kept apart from raw
    # ingredients because these are *spent*: the shelf of herbs is bottomless for now,
    # a jar of tea is not, and concentration only means anything if the pair is consumed.
    stock_used: dict[str, int] = field(default_factory=dict)

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
    # The same drawbacks, grouped and structured: one entry per poison, each with its save
    # and the effects that save gates. `drawbacks` is what a plain card shows; this is what
    # the bench draws, so the save can sit visibly in front of the harm it governs.
    poisons: list[dict] = field(default_factory=list)
    # What Purify or Neutralize took out, named. Empty unless the chain cleansed something.
    removed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    # The prose the effects were read out of, kept so nothing is lost to the summary.
    described: list[dict] = field(default_factory=list)
    # What the successful craft puts on the shelf, and what it takes off.
    output: dict | None = None
    consumes: dict[str, int] = field(default_factory=dict)
    consumes_raw: dict[str, int] = field(default_factory=dict)
    concentrating: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name, "tier": self.tier, "rank": self.rank,
            "stages": self.stages, "potency": round(self.potency, 2),
            "cleansed": self.cleansed, "risky": self.risky, "dc": self.dc,
            "chance": self.chance, "ingredients": self.ingredients,
            "effects": self.effects, "drawbacks": self.drawbacks,
            "poisons": self.poisons, "removed": self.removed,
            "problems": self.problems, "described": self.described,
            "output": self.output,
            "consumes": self.consumes, "consumes_raw": self.consumes_raw,
            "concentrating": self.concentrating,
        }


def _in_the_pot(items, used) -> list[tuple[str, str, dict]]:
    """Everything in the pot as (source, card line, spec), in order, deduplicated.

    One walk rather than two. `mechanics` read `Ingredient.lines` and `mechanical_specs`
    read `Ingredient.specs`, and nothing tied entry n of one to entry n of the other —
    harmless while every line was printed the same way, and not harmless at all now that
    the spec's *type* decides which panel its line appears in.

    Deduplicated on "source: line": two components that both cure fatigue cure it once,
    and an item that lists it twice reads as a bug on the card. Per source rather than
    globally, because two ingredients doing the same thing is a fact the card should keep.

    A held item is read from its specs, not its prose, because those carry the `from` mark
    that says which original ingredient each effect came out of — the only thing tying a
    poison's save to the damage it gates. Stock saved before `specs` existed has none, and
    falls back to the prose it does have rather than contributing nothing.
    """
    out: list[tuple[str, str, dict]] = []
    seen: set[str] = set()

    def add(source: str, line: str, spec: dict) -> None:
        key = f"{source}: {line}"
        if line and key not in seen:
            seen.add(key)
            # Marked here, once, so the spec that goes to the engine and the spec that
            # decides which panel the line lands in are the same object.
            out.append((source, line, {**spec, "from": spec.get("from") or source}
                        if spec else {}))

    for i in items:
        for line, spec in i.pairs:
            add(i.name, line, spec)
    for held, _ in used:
        if held.specs:
            for spec in held.specs:
                add(str(spec.get("from") or held.base), effectspec.render(spec), spec)
        else:
            for line in held.effects:
                add(held.base, line, {})
    return out


@dataclass
class Sifted:
    """What is in the pot, sorted into what it does for you and what it does to you.

    Measured on the shipped corpus before this existed: 99 of the 178 effects the 161
    ingredients carry are harm — damage, ability damage, conditions, penalties and the
    saves that gate them — and every one of them was printed under "Effects" beside the
    bonuses, with the saves floating free of the harm they gate. 72 of the 161 entries
    were affected.
    """
    effects: list[str] = field(default_factory=list)
    drawbacks: list[str] = field(default_factory=list)
    poisons: list[con.Poison] = field(default_factory=list)
    # Harm that gates nothing and is gated by nothing: a flat -2 to all actions.
    penalties: list[dict] = field(default_factory=list)
    specs: list[dict] = field(default_factory=list)
    # The specs that are *not* harm — what is left of the item once it has been purified.
    benefits: list[dict] = field(default_factory=list)


def sift(items, used) -> Sifted:
    """The card's two lists: what each component does for you, and what it does to you.

    Sifted out of the descriptions rather than printed whole. The source is written for a
    person — "When dried and ground into a powder, the mottled red and gray bark of this
    shrub is a boon to healers. When applied to a wound, leechwort grants a +1 alchemical
    bonus on all Heal checks..." — and a recipe card that prints both sentences buries the
    only two numbers in it.

    The chain's potency multiplier is *not* stamped on every line. It is one property of
    the result and is stated once, beside the rarity and the DC; repeating it on each
    effect was noise on every card in the app.
    """
    triples = _in_the_pot(items, used)
    specs = [spec for _, _, spec in triples if spec]
    sorted_out = con.sort_harm(specs)

    effects = [f"{source}: {line}" for source, line, spec in triples
               if not spec or any(spec is b for b in sorted_out.benefits)]
    drawbacks = [p.line for p in sorted_out.poisons]
    # Penalties are drawbacks but not poisons: a -2 to all actions hurts whoever drinks it
    # and gates nothing, so it is listed on its own rather than folded into a save it
    # never had.
    for spec in sorted_out.penalties:
        line = effectspec.render(spec)
        source = spec.get("from")
        drawbacks.append(f"{source}: {line}" if source else line)
    return Sifted(effects=effects, drawbacks=drawbacks, poisons=sorted_out.poisons,
                  penalties=sorted_out.penalties, specs=specs,
                  benefits=sorted_out.benefits)


def mechanics(items, used) -> list[str]:
    """The card's effect list — what the item does *for* you.

    Harm no longer appears here; it is a drawback, and `sift` puts it there.
    """
    return sift(items, used).effects


def mechanical_specs(items, used) -> list[dict]:
    """The same effects as `mechanics`, structured rather than rendered.

    Kept as a second function rather than changing `mechanics`'s return type, because
    `mechanics` feeds the card and callers read strings from it. This feeds the engine —
    without it a crafted potion is a paragraph, and drinking one could only ever have been
    narration. Harm included: the Drawbacks panel is a matter of presentation, and a
    poison that stopped poisoning people when it moved panels would be a worse bug than
    the one being fixed.
    """
    return sift(items, used).specs


def descriptions(items) -> list[dict]:
    """The prose the mechanics were read out of, kept for whoever wants it.

    Nothing is thrown away — a pattern that cannot claim a clause leaves it here rather
    than dropping it, so the card can be short without the detail being lost.
    """
    return [{"name": i.name, "text": i.text} for i in items if i.text]


def preview(track_id: str, level: int, chain: Chain,
            stock: dict | None = None, satchel: dict | None = None) -> Result:
    """What this chain would make, and how likely it is to work.

    Never raises for a chain that is merely bad — an empty pot, a method the character
    has not learned, an ingredient beyond their tier all come back as `problems` so the
    page can grey the button and say why. `CraftError` is for chains that cannot be
    described at all.

    `stock` is what the character has already made, so an output can go back in the pot;
    `satchel` is the raw material they are carrying. Raw ingredients are checked against
    the satchel only when one is supplied — passing None means "assume they have it",
    which is what every caller wanted before foraging existed and what the tests of the
    chain rules still want.
    """
    track = wc.get(track_id)
    level = max(1, min(int(level), track.max_level))
    known = track.unlocked_methods(level)
    ceiling = wc.tier_rank(track.at(level).max_tier)
    have: dict[str, Stock] = dict(stock or {})

    problems: list[str] = []
    items = []
    wanted: dict[str, int] = {}
    for iid in chain.ingredient_ids:
        try:
            items.append(ing_mod.get(iid))
            wanted[iid] = wanted.get(iid, 0) + 1
        except KeyError:
            problems.append(f"No such ingredient: {iid}.")

    if satchel is not None:
        for iid, n in wanted.items():
            have = int(satchel.get(iid, 0))
            if have < n:
                name = ing_mod.get(iid).name
                problems.append(f"{name}: you are carrying {have}, the chain wants {n}."
                                if have else f"You have no {name}. Forage for it.")

    used: list[tuple[Stock, int]] = []
    for sid, n in chain.stock_used.items():
        n = int(n)
        if n <= 0:
            continue
        held = have.get(sid)
        if held is None:
            problems.append(f"You are not carrying any {sid}.")
        elif held.count < n:
            problems.append(f"{held.name}: you have {held.count}, the chain wants {n}.")
        else:
            used.append((held, n))

    # Concentration: nothing but doses of one thing, at least the cost, and no raw herbs
    # muddying it. Anything else is an ordinary chain that happens to use crafted inputs.
    concentrating = (
        not items and len(used) == 1 and used[0][1] >= CONCENTRATE_COST
        and not problems
    )
    if concentrating:
        return _concentration(track, level, chain, used[0], ceiling)

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
    for held, _ in used:
        if held.rank > ceiling:
            problems.append(f"{held.name} is {held.tier}; {track.name} {level} works "
                            f"{track.at(level).max_tier} at best.")

    if not items and not used:
        problems.append("Nothing in the pot.")
    if not chain.methods:
        problems.append("No method chosen.")

    for m in chain.methods[:-1]:
        if m in FINISHING:
            problems.append(f"{m.title()} finishes a chain; nothing follows it.")

    # The result is as rare as its rarest component, which is also what gates who can
    # make it — a common chain with one legendary petal in it is a legendary brew.
    rank = max([i.rank for i in items] + [h.rank for h, _ in used], default=1)
    tier = wc.TIERS[rank - 1]

    potency = 1.0
    for m in chain.methods:
        potency *= POTENCY.get(m, 1.0)
    # A crafted input brings its own concentration with it, so a compound made from a
    # doubled tea is stronger than one made from a plain one.
    for held, n in used:
        potency *= held.potency

    cleansed = any(m in CLEANSING for m in chain.methods)
    risky = (any(i.risky for i in items) or any(h.drawbacks for h, _ in used)) \
        and not cleansed

    sifted = sift(items, used)
    effects, drawbacks = list(sifted.effects), list(sifted.drawbacks)
    poisoned = [p.as_dict() for p in sifted.poisons]
    specs = sifted.specs

    # What is dangerous about a component but has no mechanic to name. 30 of the corpus's
    # ingredients are marked risky and extract nothing harmful at all, because the danger
    # is in the harvesting rather than in the dose. Those still deserve a warning — but
    # one that says which ingredient it is about, instead of the boilerplate sentence that
    # used to be the entire Drawbacks panel however many poisons were in the pot.
    named = {p.source for p in sifted.poisons}
    rough = [i.name for i in items if i.risky and i.name not in named]
    rough += [h.name for h, _ in used if h.drawbacks and h.name not in named]

    removed: list[str] = []
    if cleansed:
        verb = " and ".join(sorted({m.title() for m in chain.methods if m in CLEANSING}))
        removed = [f"{verb} removed {p.source}'s poison: {p.body}."
                   if p.source else f"{verb} removed the poison: {p.body}."
                   for p in sifted.poisons]
        for spec in sifted.penalties:
            removed.append(f"{verb} removed {effectspec.render(spec)} "
                           f"({spec.get('from') or 'the mixture'}).")
        if rough:
            removed.append(f"{verb} removed the handling risks of "
                           f"{', '.join(sorted(set(rough)))}.")
        if not removed:
            removed = [f"{verb} found nothing harmful to remove."]
        # Struck from the item itself, not only from the card. Before this, purifying set
        # a flag and appended a sentence while the harmful specs stayed on the Stock — so
        # a "Purified Draught of Skull Orchid" still did every point of its Constitution
        # damage when somebody drank it, and could still be thrown at people. The method
        # that the author says "completely removes its negative side effects" removed
        # nothing whatsoever.
        specs = list(sifted.benefits)
        drawbacks = []
        poisoned = []
        # Kept on the effect list rather than only on the preview, so the jar in the
        # satchel says what was taken out of it long after the bench is closed.
        effects = effects + removed
    elif rough:
        drawbacks.append(
            f"Untreated hazardous components: {', '.join(sorted(set(rough)))}. "
            f"Harvesting and handling risks still apply. "
            f"Purify or Neutralize removes them.")

    dc = _dc(items, rank, chain.stages)
    name = chain.name or _name_for(items or [h for h, _ in used], chain.methods)
    out = Stock(base=name, concentration=1, tier=tier, potency=potency,
                craft=track.id, effects=effects, drawbacks=drawbacks,
                specs=specs,
                from_ingredients=[i.id for i in items]
                + [h.id for h, _ in used])
    return Result(
        name=name, tier=tier, rank=rank, stages=chain.stages, potency=potency,
        cleansed=cleansed, risky=risky, dc=dc,
        chance=_chance(dc, level, rank, problems),
        ingredients=[i.as_dict() for i in items] + [h.as_dict() for h, _ in used],
        effects=effects, drawbacks=drawbacks, poisons=poisoned, removed=removed,
        problems=problems,
        described=descriptions(items),
        output=out.as_dict(),
        consumes={h.id: n for h, n in used},
        consumes_raw=dict(wanted),
    )


def _concentration(track, level: int, chain: Chain,
                   pair: tuple[Stock, int], ceiling: int) -> Result:
    """Two doses in, one of twice the strength out.

    A trade of quantity for density, not a gain — which is why the pair is spent and the
    output count is one. The rarity step is what makes it a ladder rather than a loop:
    each concentration is a band rarer, so Tier 3 is rare material and working rare
    material is Herbalist 3.
    """
    held, want = pair
    spend = (want // CONCENTRATE_COST) * CONCENTRATE_COST
    made = concentrate(held)

    problems = []
    if held.rank > ceiling:
        problems.append(f"{held.name} is {held.tier}; {track.name} {level} works "
                        f"{track.at(level).max_tier} at best.")
    # Concentrating is what `distill` is for. Requiring it is what keeps the ladder
    # behind the track rather than available to anyone with two jars.
    if "distill" not in chain.methods:
        problems.append("Concentrating is distilling — put the still in the chain.")
    elif "distill" not in track.unlocked_methods(level):
        need = next(l.level for l in sorted(track.levels, key=lambda x: x.level)
                    if "distill" in l.methods)
        problems.append(f"Distill is learned at {track.name} {need}.")

    # Through `_dc` rather than open-coded, because this was a second copy of the same
    # rule and the two had drifted apart: `_dc` reads `5 + 5 * rank` and this read
    # `10 + 5 * rank`, five harder for no reason either one gave. The five mattered at
    # exactly one place — the top rung. A crafter's whole bonus is `3 * level`, so at
    # Herbalist 5 it is +15, and DC 35 needed a 20 on the d20: the last step of the
    # ladder sat at the 5% floor at *every* level, master or not, while each attempt ate
    # two doses. Aligned, the same step is 15% at Herbalist 4 and 30% at Herbalist 5.
    dc = _dc([], made.rank, chain.stages)
    return Result(
        name=made.name, tier=made.tier, rank=made.rank, stages=max(1, chain.stages),
        potency=made.potency, cleansed=False, risky=bool(made.drawbacks),
        dc=dc, chance=_chance(dc, level, made.rank, problems),
        ingredients=[held.as_dict()],
        effects=list(made.effects),
        drawbacks=made.drawbacks,
        poisons=[p.as_dict() for p in con.poisons(made.specs, source=made.base)],
        problems=problems, described=[],
        output=made.as_dict(), consumes={held.id: spend}, concentrating=True,
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


SHAPE_WORDS = {
    "grind": "Powder", "mix": "Compound", "brew": "Tea", "preserve": "Preserve",
    "extract": "Extract", "distill": "Tincture", "purify": "Purified Draught",
    "infuse": "Infusion", "neutralize": "Neutralised Draught", "refine": "Elixir",
    "catalyst crafting": "Catalyst",
}


def _name_for(items, methods) -> str:
    """A working name, so the preview is not headed "Untitled".

    The shape word replaces any shape word already on the end of the lead ingredient's
    name rather than stacking on top of it. Crafted outputs go back into the craft tree as
    inputs — that is the whole point of keeping them in inventory — so distilling a
    tincture used to produce a "Dragon Flower Tincture Tincture", and ten passes produced
    exactly what you would expect. Seen in play, ten deep.
    """
    if not items:
        return "Empty pot"
    lead = items[0].name
    for word in sorted(set(SHAPE_WORDS.values()) | {"Preparation"},
                       key=len, reverse=True):
        # Strip repeatedly: a name that already compounded before this fix should come
        # back to something sensible the next time it is crafted with.
        while lead.lower().endswith(" " + word.lower()):
            lead = lead[: -(len(word) + 1)].rstrip()
    last = methods[-1] if methods else ""
    shape = SHAPE_WORDS.get(last, "Preparation")
    return f"{lead} {shape}".strip()
