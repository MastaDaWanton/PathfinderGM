"""Blacksmithing chains: what a charge of metal and a sequence of forge work produces.

The second world class, and the proof of `rules/worldclass.py`'s claim that blacksmithing
is "three more files rather than three more code paths": the track is a JSON file the
generic loader reads unchanged, the materials are a content file shaped like the herb
corpus, and this module is the only new code — the chain semantics, mirroring
`rules/crafting.py`'s concepts (ordered methods, cleansing, finishing, problems-lists
that refuse before rolling) without inheriting any of its herb specifics.

The naming mirrors `crafting.py` deliberately — `TRACK_ID`, `CraftError`, `Chain`,
`preview` — so a later dispatch layer can route a craft to whichever module owns the
track without either module knowing about the other.

One rule is stated here because the source documents state percentages without one:

  Costs and penalties round **down**, benefits round **up**. A character is never
  surprised in the direction that hurts them — a mithral longsword at half of 4 lb is
  2 lb, and half of 5 lb is 2 lb too, because weight is a cost.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import effectspec
from . import worldclass as wc

TRACK_ID = "blacksmith"

# Methods that burn fuel. A chain that lights no fire needs none: riveting a grip onto a
# finished blade is cold work.
FUEL_BURNING = ("smelt", "forge")

# Smelting past this rank needs a fuel of at least `HOT_FUEL_RANK`: adamantine does not
# melt over charcoal. Rank 3 is "rare", so the skymetals (exotic and up) are the ones
# gated — which is the whole point of dragonfire coal existing as an entry.
HOT_METAL_RANK = 4
HOT_FUEL_RANK = 3

# Methods that remove a drawback rather than shaping metal — `flux` is to dirty ore what
# `purify` is to a poisonous herb. It cleans the *metal*, not the smith: the harm it
# strips is the harm carried by ore-kind materials, and a metal that sickens whoever
# works it (abysium) stays risky however much flux goes in the melt.
CLEANSING = ("flux",)

# The method that has to come last if it is used at all: you polish the finished piece,
# you do not forge the polish.
FINISHING = ("polish",)

# Each method's prerequisite, which must appear *earlier in the same chain*. This is the
# physical grammar of the forge — you cannot quench what was never forged — and it is
# what makes a chain an ordered list rather than a bag of verbs.
AFTER = {
    "quench": "forge",
    "temper": "quench",   # tempering is letting quenched steel back down
    "fold": "forge",
    "draw": "forge",
    "hone": "forge",
    "polish": "hone",     # a mirror finish is the last grade of an honed edge
    "alloy": "smelt",     # alloying happens in the melt, so something must be molten
}

# Sentences for the refusals above, written once so the bench and the tests cannot
# disagree about the wording. {m} is the method, {need} its prerequisite.
_AFTER_WHY = {
    "quench": "You cannot quench what was never forged — quench follows forge.",
    "temper": "Tempering lets quenched steel back down — temper follows quench.",
    "fold": "Folding doubles hot metal over itself — fold follows forge.",
    "draw": "Drawing pulls forged stock through the plate — draw follows forge.",
    "hone": "Honing grinds a forged edge — hone follows forge.",
    "polish": "Polish is the last grade of an honed surface — polish follows hone.",
    "alloy": "Alloying happens in the melt — alloy follows smelt.",
}

# Metals that refuse the crucible. What makes them what they are does not survive being
# melted into something else — cold iron alloyed is only iron. Data-adjacent but kept in
# code rather than per-entry flags, because the rule is about *pairs* and a flag on one
# entry cannot say "not with anything".
SOLITARY = frozenset({
    "cold-iron", "cold-iron-ore", "mithral", "mithral-ore",
    "adamantine", "adamantine-ore", "noqual", "noqual-ore",
    "inubrix", "inubrix-ore", "horacalcum", "horacalcum-ore",
})

# A novel alloy is a discovery: melting two *different* metals of the same tier yields a
# metal one band rarer. This is the blacksmith's counterpart to the Herbalist's
# concentration ladder, and for the same structural reason — it is the one way a
# Blacksmith 4 reaches legendary metal, which the level-5 deed requires. Without it the
# milestone gate could never open, which is the exact bug the Herbalist deed notes.
ALLOY_RARITY_STEP = 1

# Material kinds that count as metal for alloying and for "is there anything to work".
METAL_KINDS = ("ore", "metal", "alloy")


def round_cost(x: float) -> int:
    """Costs and penalties round down — the direction that favours the character."""
    return int(math.floor(x))


def round_benefit(x: float) -> int:
    """Benefits round up, so 80% of a 1-point bonus is 1 rather than a silent 0."""
    return int(math.ceil(x))


class CraftError(ValueError):
    """The chain cannot be attempted. Raised before anything is scored, so a chain the
    character cannot make never advances their track."""


# --- materials -----------------------------------------------------------------------------

@dataclass
class Material:
    """One entry of the smith's stock list — ore, metal, fuel, flux, quenchant, fitting
    or treatment. Shaped after `ingredients.Ingredient` on purpose: same tier vocabulary,
    same authored-effects-first rule, same `effects_converted` honesty flag."""
    id: str
    name: str
    kind: str = "metal"        # ore | metal | alloy | fuel | flux | quenchant
                               #   | fitting | treatment
    tier: str = "common"
    craft_dc: int | None = None
    text: str = ""
    risky: bool = False
    source: str = "bought"     # mined | bought | harvested | monster
    biomes: list[str] = field(default_factory=list)
    effects: list = field(default_factory=list)
    effects_converted: bool = False
    # What working this into a piece does to the piece's weight. Not an effect, because
    # `effectspec` has no vocabulary for it — it is a property of the object, applied
    # with the rounding rule (weight is a cost, so it rounds down).
    weight_factor: float = 1.0

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def specs(self) -> list[dict]:
        return [dict(e) for e in self.effects]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "craft_dc": self.craft_dc, "text": self.text,
            "risky": self.risky, "source": self.source, "biomes": self.biomes,
            "effects": self.effects, "effects_converted": self.effects_converted,
            "weight_factor": self.weight_factor,
        }


def from_dict(d: dict) -> Material:
    return Material(
        id=d["id"], name=d["name"], kind=d.get("kind", "metal"),
        tier=d.get("tier", "common"), craft_dc=d.get("craft_dc"),
        text=d.get("text", ""), risky=bool(d.get("risky")),
        source=d.get("source", "bought"),
        biomes=list(d.get("biomes") or []),
        effects=list(d.get("effects") or []),
        effects_converted=bool(d.get("effects_converted")),
        weight_factor=float(d.get("weight_factor", 1.0)),
    )


def load_dir(path: str | Path) -> dict[str, dict]:
    """Raw entries from a directory, as dicts so shipped and homebrew merge before build.

    Two shapes, for the same reason `registry.read_folder` accepts two: the shipped
    corpus is one file holding a list under "materials", and a homebrew drop-in is most
    naturally one file holding one entry. Reading only the first shape is the failure the
    registry's docstring records — a save that appears in an editor and never reaches
    play, with no error anywhere.
    """
    out: dict[str, dict] = {}
    p = Path(path)
    if not p.is_dir():
        return out
    for file in sorted(p.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries = data.get("materials") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            entries = [data] if isinstance(data, dict) and data.get("id") else []
        for raw in entries:
            if isinstance(raw, dict) and raw.get("id"):
                out[str(raw["id"]).strip().lower()] = raw
    return out


_MATERIALS: dict[str, Material] | None = None


def materials(refresh: bool = False) -> dict[str, Material]:
    """Every material the smith can name, shipped and homebrew.

    Homebrew is layered over the shipped set rather than replacing it, so a corrected
    entry in a later build is not shadowed by a stale copy in the user's data
    directory — the trap `CLAUDE.md` records from World Bible's stylesheet. Same pattern
    as `worldclass.tracks()`, and not routed through `rules.registry` because
    registering a Kind would touch a shared file other tracks are editing in parallel;
    the registration is listed in docs/blacksmithing.md's integration notes instead.

    `refresh` drops the cache — for tests that write a homebrew file and need the next
    read to see it, and for a bench that just saved one.
    """
    global _MATERIALS
    if refresh:
        _MATERIALS = None
    if _MATERIALS is None:
        from django.conf import settings

        raw = load_dir(Path(settings.BASE_DIR) / "content" / "materials")
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
        if user.is_dir():
            # Merged field by field rather than replaced, like `registry.load_raw`: a
            # homebrew file that corrects one field must not silently erase five.
            for key, entry in load_dir(user).items():
                merged = dict(raw.get(key, {}))
                merged.update(entry)
                raw[key] = merged
        _MATERIALS = {k: from_dict({**v, "id": k}) for k, v in raw.items()}
    return _MATERIALS


def get(material_id: str) -> Material:
    m = materials().get((material_id or "").strip().lower())
    if m is None:
        raise KeyError(f"no material {material_id!r}")
    return m


# --- the base item -------------------------------------------------------------------------

def base_item(ref: str) -> dict | None:
    """The thing being made, from the real equipment tables.

    A weapon id from `content/weapons/weapons.json` or an armour name from
    `tables.ARMOUR` — never a free-text invention, for the same reason ingredients
    ground every name: given freedom, output invents items that do not exist and then
    treats them as settled fact.
    """
    from . import weapons
    from .tables import ARMOUR

    key = (ref or "").strip().lower()
    if not key:
        return None
    if weapons.has(key):
        w = weapons.get(key)
        return {"id": key, "name": w.get("name", key), "family": "weapon",
                "weight_lb": w.get("weight_lb"), "damage": w.get("damage", "")}
    if key in ARMOUR:
        a = ARMOUR[key]
        return {"id": key, "name": a.get("name", key), "family": "armour",
                "weight_lb": None, "acp": a.get("acp", 0)}
    return None


# --- chains --------------------------------------------------------------------------------

@dataclass
class Chain:
    """One piece of forge work: methods in order, materials in the charge, and the base
    item being made. `base` names a weapon id or an armour key — the shape of the thing;
    the materials are what it is made *of*."""
    track: str
    methods: list[str] = field(default_factory=list)
    material_ids: list[str] = field(default_factory=list)
    base: str = ""
    name: str = ""

    @property
    def stages(self) -> int:
        return len(self.methods)


# The quality ladder, decided by which methods the chain contains. Masterwork is the
# book's own rule made procedural: Craft says a masterwork component is its own DC-20
# piece of work, and here that work is named — the steel must be tempered, shaped past
# plain forging (fold or draw), and finished (hone or polish). Fine is the honest step
# between: tempered and finished, but not pattern-worked.
MASTERWORK_DC = 20


def quality_of(methods: list[str]) -> str:
    tempered = "temper" in methods
    shaped = "fold" in methods or "draw" in methods
    finished = "hone" in methods or "polish" in methods
    if tempered and shaped and finished:
        return "masterwork"
    if tempered and finished:
        return "fine"
    return "plain"


# What each quality writes on the finished piece. Masterwork is PF1e's rule verbatim: a
# masterwork weapon adds +1 enhancement on attack rolls (not damage), and masterwork
# armour lessens its check penalty by 1. The armour half is narrative because ACP is not
# in the effect vocabulary; the note says exactly what the GM applies.
def _quality_specs(quality: str, family: str) -> list[dict]:
    if quality != "masterwork":
        return []
    if family == "armour":
        return [{"type": "narrative",
                 "target": "Masterwork: armour check penalty is lessened by 1"}]
    return [{"type": "combat_mod", "amount": 1, "bonus_type": "enhancement",
             "target": "attack", "note": "(masterwork)"}]


@dataclass
class Result:
    """What the chain would make. Same contract as `crafting.Result`: `problems` empty
    means the work can be attempted; nothing here rolls anything."""
    name: str
    tier: str
    rank: int
    quality: str
    stages: int
    dc: int
    risky: bool
    weight_lb: int | None
    base: dict | None
    effects: list[str]
    specs: list[dict]
    removed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    consumes: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "name": self.name, "tier": self.tier, "rank": self.rank,
            "quality": self.quality, "stages": self.stages, "dc": self.dc,
            "risky": self.risky, "weight_lb": self.weight_lb, "base": self.base,
            "effects": self.effects, "specs": self.specs, "removed": self.removed,
            "problems": self.problems, "consumes": self.consumes,
        }


def preview(level: int, chain: Chain, stock: dict | None = None) -> Result:
    """What this chain would forge, and everything wrong with attempting it.

    Never raises for a chain that is merely bad — an unknown method, metal above the
    smith's tier, a cold forge all come back as `problems` so the page can grey the
    button and say why, exactly as `crafting.preview` does. `CraftError` is reserved for
    chains that cannot be described at all.

    `stock` is what the smith is carrying, as {material id: count}. Passing None means
    "assume they have it" — what every caller wants until acquisition (mining, buying)
    exists, and what the tests of the chain rules want forever.
    """
    track = wc.get(TRACK_ID)
    level = max(1, min(int(level), track.max_level))
    known = track.unlocked_methods(level)
    ceiling = wc.tier_rank(track.at(level).max_tier)

    problems: list[str] = []
    items: list[Material] = []
    wanted: dict[str, int] = {}
    for mid in chain.material_ids:
        try:
            items.append(get(mid))
            wanted[mid] = wanted.get(mid, 0) + 1
        except KeyError:
            problems.append(f"No such material: {mid}.")

    if stock is not None:
        for mid, n in wanted.items():
            carrying = int(stock.get(mid, 0))
            if carrying < n:
                name = get(mid).name
                problems.append(
                    f"{name}: you are carrying {carrying}, the chain wants {n}."
                    if carrying else f"You have no {name}.")

    for m in chain.methods:
        if m not in track.unlocked_methods(track.max_level):
            problems.append(f"{track.name} has no method called {m!r}.")
        elif m not in known:
            need = next(l.level for l in sorted(track.levels, key=lambda x: x.level)
                        if m in l.methods)
            problems.append(f"{m.title()} is learned at {track.name} {need}.")

    if not chain.methods:
        problems.append("No method chosen.")
    if not items:
        problems.append("Nothing in the charge.")

    metals = [i for i in items if i.kind in METAL_KINDS]
    if items and not metals:
        problems.append("Nothing to work: no ore, metal or alloy in the charge.")

    base = base_item(chain.base)
    if chain.base and base is None:
        problems.append(
            f"No such base item {chain.base!r}: name a weapon from the weapons list "
            f"or an armour by name.")
    if not chain.base and any(m in ("forge", "rivet") for m in chain.methods):
        problems.append("Forging needs a shape: say what is being made.")

    # The physical grammar: each method's prerequisite must already have happened.
    for at, m in enumerate(chain.methods):
        need = AFTER.get(m)
        if need and need not in chain.methods[:at]:
            problems.append(_AFTER_WHY[m])

    for m in chain.methods[:-1]:
        if m in FINISHING:
            problems.append(f"{m.title()} finishes a piece; nothing follows it.")

    # Fire needs feeding, and skymetal fire needs better food than charcoal.
    fuels = [i for i in items if i.kind == "fuel"]
    if any(m in FUEL_BURNING for m in chain.methods) and not fuels:
        problems.append("The forge is cold: smelting and forging burn fuel, and there "
                        "is none in the charge.")
    if "smelt" in chain.methods and fuels:
        hottest = max(f.rank for f in fuels)
        for i in metals:
            if i.rank >= HOT_METAL_RANK and hottest < HOT_FUEL_RANK:
                problems.append(
                    f"{i.name} does not melt over {fuels[0].name.lower()}: smelting "
                    f"{i.tier} metal needs a fuel of rare tier or better.")

    # Alloying: at least two metals, and none of the solitary ones.
    if "alloy" in chain.methods:
        if len(metals) < 2:
            problems.append("Alloying combines metals, and there are not two in the "
                            "charge.")
        for i in metals:
            if i.id in SOLITARY and len(metals) > 1:
                others = ", ".join(sorted(m.name for m in metals if m is not i))
                problems.append(
                    f"{i.name} works alone: melted together with {others} it is only "
                    f"dead metal — what makes it {i.name.lower()} does not survive "
                    f"the mixing.")
                break

    # The result is as rare as its rarest component — and a novel alloy of two distinct
    # same-tier metals is one band rarer than either, which is the Blacksmith 4 path to
    # the legendary deed (see the track file's _deeds_note). The ceiling is checked
    # against the *inputs*, never the stepped-up output, exactly as the Herbalist's
    # concentration ladder checks the held jar and not the rarer one it makes: gating on
    # the output would re-create the unreachable-deed bug that ladder exists to avoid.
    rank = max((i.rank for i in items), default=1)
    tops = {i.id for i in metals if i.rank == rank}
    if ("alloy" in chain.methods and len(tops) >= 2
            and not tops & SOLITARY):
        rank = min(len(wc.TIERS), rank + ALLOY_RARITY_STEP)
    tier = wc.TIERS[rank - 1]

    for i in items:
        if i.rank > ceiling:
            problems.append(f"{i.name} is {i.tier}; {track.name} {level} works "
                            f"{track.at(level).max_tier} at best.")

    quality = quality_of(chain.methods)
    dc = _dc(items, rank, chain.stages)
    if quality == "masterwork":
        # The book's own number: a masterwork component is a DC 20 piece of work in its
        # own right, so the chain is never easier than that.
        dc = max(dc, MASTERWORK_DC)

    # Effects: what every material contributes, plus what the quality adds. Flux strips
    # the harm carried by dirty ore, the way purify strips a poison — but only from ore:
    # a metal that sickens the smith (abysium) is not cleaner for the slag being gone.
    cleansed = any(m in CLEANSING for m in chain.methods)
    specs: list[dict] = []
    effects: list[str] = []
    removed: list[str] = []
    from . import consumables as con

    for i in items:
        for spec in i.specs:
            marked = {**spec, "from": spec.get("from") or i.name}
            if cleansed and i.kind == "ore" and con.hurts(marked):
                removed.append(f"Flux carried off {i.name}'s impurity: "
                               f"{effectspec.render(spec)}.")
                continue
            specs.append(marked)
            effects.append(f"{i.name}: {effectspec.render(spec)}")

    family = (base or {}).get("family", "weapon")
    for spec in _quality_specs(quality, family):
        specs.append(spec)
        effects.append(effectspec.render(spec))

    risky = any(i.risky for i in items)

    # Weight: the base item's, scaled by every material's factor, rounded as a cost.
    weight = None
    if base and base.get("weight_lb"):
        factor = 1.0
        for i in items:
            factor *= i.weight_factor
        weight = max(0, round_cost(float(base["weight_lb"]) * factor))

    name = chain.name or _name_for(items, base, quality)
    return Result(
        name=name, tier=tier, rank=rank, quality=quality, stages=chain.stages,
        dc=dc, risky=risky, weight_lb=weight, base=base,
        effects=effects, specs=specs, removed=removed, problems=problems,
        consumes=dict(wanted),
    )


def _dc(items: list[Material], rank: int, stages: int) -> int:
    """Hardest material sets the floor; length of the chain adds to it.

    The same shape as `crafting._dc`, deliberately not the same function: materials that
    carry their own DC use it — an authored number beats a derived one — and the rest
    fall back on their tier at 5 + 5 × rank, plus 2 per stage beyond the first.
    """
    stated = [i.craft_dc for i in items if i.craft_dc is not None]
    base = max(stated) if stated else 5 + 5 * rank
    return base + 2 * max(0, stages - 1)


def _name_for(items: list[Material], base: dict | None, quality: str) -> str:
    """A working name — "Masterwork Cold Iron Longsword" — so the preview is never
    headed "Untitled". The lead metal names the piece; refined metal and alloys outrank
    ore, because a sword smelted from cold iron ore is a cold iron sword, not an ore
    sword."""
    lead = next((i for i in items if i.kind in ("metal", "alloy")),
                next((i for i in items if i.kind == "ore"), None))
    shape = (base or {}).get("name", "work")
    metal = ""
    if lead is not None:
        metal = lead.name
        if lead.kind == "ore" and metal.lower().endswith(" ore"):
            metal = metal[:-4]
    prefix = {"masterwork": "Masterwork ", "fine": "Fine "}.get(quality, "")
    return f"{prefix}{metal} {shape}".replace("  ", " ").strip().title()
