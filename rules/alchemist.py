"""Alchemy chains: what a set of materials and a sequence of laboratory verbs produces.

The Herbalist's nearest sibling, and deliberately shaped like `rules/crafting.py` — the
same public surface (`TRACK_ID`, `CraftError`, `Chain`, `preview`, `materials`) so a later
dispatcher can route a chain to whichever craft owns it without learning two vocabularies.
The *methods* do not overlap: herbalism owns grind/brew/distill/infuse/purify, and this
module owns the laboratory's verbs — calcine, dissolve, filter, precipitate, react,
sublime, catalyze, stabilize, seal.

Namespace note: "alchemist" here is the WORLD CLASS (`rules.worldclass.get("alchemist")`),
not the PF1e Alchemist character class in `content/classes/`. Same word, separate
namespaces, and they never meet in code.

Two rules carry over from crafting.py because they are house law, not herbalism law:

  Costs and penalties round **down**, benefits round **up**. Potency is carried as a
  float here and applied at use time by `rules/consumables.scale`, which already rounds
  the house way.

What is new is **volatility**, because volatility is alchemy's signature the way
foraging is herbalism's. A volatile material is one that fights back on the bench:
each volatile past the first raises the DC (`VOLATILE_DC_STEP`) and raises the mishap
stakes, and the numbers are itemised in the preview the same way `crafting.check_terms`
itemises the bonus — a player who can see the terms can see what would improve them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import consumables as con
from . import effectspec
from . import worldclass as wc

TRACK_ID = "alchemist"


class CraftError(ValueError):
    """The chain cannot be described at all. Raised before anything is scored, so a
    chain the character cannot make never advances their track. Merely *bad* chains —
    unknown material, ungated tier, two volatiles and no stabilizer — come back as
    `problems` instead, so the page can grey the button and say why."""


# Methods that change what a preparation is worth, as multipliers on its potency.
# React and sublime match herbalism's distill/refine at 1.25 on purpose: the two tracks
# pay mastery from the same table, so a stage here must be worth what a stage there is.
# Catalyze is the level-5 method and pays like one.
POTENCY = {
    "react": 1.25,      # "+25% to the primary effect" — the dangerous heart of the craft
    "sublime": 1.25,    # vapour to crystal, everything gross left behind
    "catalyze": 1.50,   # "preparations at 150% of base strength"
}

# The method that removes a material's drawback rather than scaling it.
CLEANSING = ("filter",)

# The method that has to come last if it is used at all: you seal the finished work,
# you do not calcine the sealed flask.
FINISHING = ("seal",)

# Each volatile material past the first adds this to the DC. One volatile is the trade
# working as intended; the second is two tempers in one vessel. +3 rather than +2 so the
# surcharge is visibly not the per-stage bump — a player reading the itemised DC should
# be able to tell which number is which.
VOLATILE_DC_STEP = 3

# What each method names its output. Chosen to never collide with herbalism's
# `crafting.SHAPE_WORDS` (Powder, Tea, Tincture, Infusion, Elixir, Catalyst...), because
# `is_tincture` and friends read shape words off jar names and a colliding word would
# make an alchemist's product answer herbalism's questions.
SHAPE_WORDS = {
    "calcine": "Calx", "dissolve": "Solution", "filter": "Filtrate",
    "precipitate": "Precipitate", "react": "Admixture", "sublime": "Sublimate",
    "catalyze": "Arcanum", "seal": "Sealed Flask",
    # stabilize shapes nothing — it is how a reaction is survived, not what it makes.
}


# --- materials -----------------------------------------------------------------------------


@dataclass
class Material:
    """One thing on the alchemist's shelf. The same shape as `ingredients.Ingredient`
    where the fields mean the same thing, plus the two flags that are alchemy's own:
    `volatile` (counts toward the DC surcharge and the two-in-a-vessel rule) and
    `needs_stabilizer` (attacks its own vessel — alkahest, phlogiston, a starfall core)."""
    id: str
    name: str
    kind: str = "reagent"       # reagent | solvent | catalyst | salt | essence | gland
                                #  | vessel | treatment | intermediate
    tier: str = "common"
    craft_dc: int | None = None
    text: str = ""
    risky: bool = False
    volatile: bool = False
    needs_stabilizer: bool = False
    effects: list = field(default_factory=list)
    effects_converted: bool = False

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def specs(self) -> list[dict]:
        """Structured effects, each marked with where it came from — the mark is the
        only thing tying a poison's save to the damage it gates once specs from several
        materials share one pot (see `consumables.poisons`)."""
        return [{**dict(e), "from": dict(e).get("from") or self.name}
                for e in self.effects]

    @property
    def lines(self) -> list[str]:
        return [effectspec.render(s) for s in self.specs]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "craft_dc": self.craft_dc, "text": self.text,
            "risky": self.risky, "volatile": self.volatile,
            "needs_stabilizer": self.needs_stabilizer,
            "effects": self.effects, "lines": self.lines,
        }


def from_dict(d: dict) -> Material:
    return Material(
        id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "reagent"),
        tier=d.get("tier", "common"), craft_dc=d.get("craft_dc"),
        text=d.get("text", ""), risky=bool(d.get("risky")),
        volatile=bool(d.get("volatile")),
        needs_stabilizer=bool(d.get("needs_stabilizer")),
        effects=list(d.get("effects") or []),
        effects_converted=bool(d.get("effects_converted")),
    )


def load_dir(path: str | Path) -> dict[str, dict]:
    """Raw entries from a directory, as dicts so they can be merged before being built.

    Two shapes, for the same reason `ingredients.load_dir` takes two: the shipped
    catalogue is one file holding a list under "materials", and a homebrew editor will
    write one file per thing it edits.
    """
    out: dict[str, dict] = {}
    for p in sorted(Path(path).glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries = data.get("materials") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            entries = [data] if isinstance(data, dict) and data.get("id") else []
        for raw in entries:
            if raw.get("id"):
                out[raw["id"]] = raw
    return out


_MATERIALS: dict[str, Material] | None = None


def materials() -> dict[str, Material]:
    """Every material the bench knows, shipped and homebrew.

    Homebrew is layered over the shipped set rather than replacing it, so a corrected
    catalogue in a later build is not shadowed by a stale copy in the user's data
    directory — the trap `CLAUDE.md` records from World Bible's stylesheet, and the
    exact pattern `worldclass.tracks()` uses for the same reason.
    """
    global _MATERIALS
    if _MATERIALS is None:
        from django.conf import settings

        raw = load_dir(Path(settings.BASE_DIR) / "content" / "materials")
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
        if user.is_dir():
            raw.update(load_dir(user))
        _MATERIALS = {k: from_dict({**v, "id": k}) for k, v in raw.items()}
    return _MATERIALS


# The words herbalism's methods write onto their products, as they appear inside a stock
# id — read from `crafting.SHAPE_WORDS` rather than copied, because a copied list is the
# stale-copy bug CLAUDE.md warns about ("grep for every copy of it"), and the whole point
# of the cross-craft hook is that crafting.py stays the one authority on what it makes.
def _herbal_shape_slugs() -> list[str]:
    from . import crafting

    words = {w.lower().replace(" ", "-") for w in crafting.SHAPE_WORDS.values()}
    words.add("preparation")
    return sorted(words, key=len, reverse=True)


def _intermediate(material_id: str) -> Material | None:
    """A herbalism-crafted input, recognised by the name its craft wrote on it.

    An infusion is a reagent: the author's crafts are meant to feed each other, and a
    "Woundwort Tincture" is exactly the kind of prepared liquid a reaction wants as its
    medium. Recognised by id shape — the slug ends with (or contains) one of herbalism's
    shape words, optionally carrying crafting.Stock's "#concentration" suffix — because
    the id is the only thing a chain hands us, and the shape word is the one part of it
    the other craft guarantees.

    Tier defaults to common: the id does not carry the jar's tier, and guessing higher
    would let an id string bypass the tier gate that real stock is checked against.
    """
    slug = str(material_id or "").split("#")[0].strip().lower()
    if not slug:
        return None
    parts = slug.split("-")
    if not any(word in "-".join(parts) and (
            slug.endswith(word) or f"-{word}-" in f"-{slug}-")
            for word in _herbal_shape_slugs()):
        return None
    liquid = any(shape.lower().replace(" ", "-") in slug for shape in _liquid_shapes())
    return Material(
        id=str(material_id), name=slug.replace("-", " ").title(),
        kind="intermediate", tier="common",
        # A liquid intermediate can be a reaction's medium; see `_react_problems`.
        text="A herbalism-crafted input, accepted as a reagent."
             + (" It pours." if liquid else ""),
    )


def _liquid_shapes() -> set[str]:
    from . import crafting

    return set(crafting.LIQUID_SHAPES)


def get(material_id: str) -> Material:
    m = materials().get((material_id or "").strip().lower())
    if m is not None:
        return m
    made = _intermediate(material_id)
    if made is not None:
        return made
    raise KeyError(f"no material {material_id!r}")


# --- chains --------------------------------------------------------------------------------


@dataclass
class Chain:
    """An ordered list of laboratory verbs applied to a set of materials — the chain is
    the thing that gets validated, not a recipe. Same shape as `crafting.Chain` minus
    the track field, because this module only ever speaks for one track."""
    methods: list[str] = field(default_factory=list)
    material_ids: list[str] = field(default_factory=list)
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
    dc: int
    # The DC itemised, the way `crafting.check_terms` itemises the bonus: "+3 second
    # volatile" is a sentence the player can act on, and a bare 19 is one they must trust.
    dc_terms: list[dict]
    # The volatile materials by name, so the bench can mark the jars that are the reason.
    volatiles: list[str]
    # What failure costs, in words that scale with the volatility. "" when a failed roll
    # is only wasted material.
    mishap: str
    risky: bool
    cleansed: bool
    effects: list[str]
    drawbacks: list[str]
    specs: list[dict] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    materials: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "name": self.name, "tier": self.tier, "rank": self.rank,
            "stages": self.stages, "potency": round(self.potency, 2),
            "dc": self.dc, "dc_terms": self.dc_terms, "volatiles": self.volatiles,
            "mishap": self.mishap, "risky": self.risky, "cleansed": self.cleansed,
            "effects": self.effects, "drawbacks": self.drawbacks, "specs": self.specs,
            "removed": self.removed, "problems": self.problems,
            "materials": self.materials,
        }


def preview(level: int, chain: Chain, stock: dict | None = None) -> Result:
    """What this chain would make, and what could go wrong, without rolling anything.

    Mirrors `crafting.preview`'s contract: never raises for a chain that is merely bad —
    every refusal comes back in `problems` so the page can grey the button and say why.
    `stock` is what the character is carrying, as {material id: count}; passing None
    means "assume they have it", which is what the chain-rule tests want.
    """
    if chain is None:
        raise CraftError("no chain to preview")
    track = wc.get(TRACK_ID)
    level = max(1, min(int(level), track.max_level))
    known = track.unlocked_methods(level)
    ceiling = wc.tier_rank(track.at(level).max_tier)

    problems: list[str] = []
    mats: list[Material] = []
    wanted: dict[str, int] = {}
    for mid in chain.material_ids:
        try:
            mats.append(get(mid))
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

    for m in mats:
        if m.rank > ceiling:
            problems.append(f"{m.name} is {m.tier}; {track.name} {level} works "
                            f"{track.at(level).max_tier} at best.")

    if not mats:
        problems.append("Nothing on the bench.")
    if not chain.methods:
        problems.append("No method chosen.")

    for m in chain.methods[:-1]:
        if m in FINISHING:
            problems.append(f"{m.title()} finishes a chain; nothing follows it.")

    problems.extend(_seal_problems(chain.methods))
    problems.extend(_react_problems(mats, chain.methods))

    volatiles = [m.name for m in mats if m.volatile]
    problems.extend(_volatile_problems(mats, volatiles, chain.methods))

    # The result is as rare as its rarest material — the same rule as crafting.py, and
    # what gates who can make it.
    rank = max([m.rank for m in mats], default=1)
    tier = wc.TIERS[rank - 1]

    potency = 1.0
    for m in chain.methods:
        potency *= POTENCY.get(m, 1.0)

    dc_terms = _dc_terms(mats, rank, chain.stages, len(volatiles))
    dc = sum(t["value"] for t in dc_terms)

    cleansed = any(m in CLEANSING for m in chain.methods)
    specs = [s for m in mats for s in m.specs]
    sorted_out = con.sort_harm(specs)
    effects = [f"{s.get('from')}: {effectspec.render(s)}"
               for s in sorted_out.benefits]
    drawbacks = [p.line for p in sorted_out.poisons]
    for spec in sorted_out.penalties:
        source = spec.get("from")
        line = effectspec.render(spec)
        drawbacks.append(f"{source}: {line}" if source else line)

    removed: list[str] = []
    if cleansed:
        # Filtering strips harm from the specs themselves, not only from the card —
        # the lesson crafting.py's purify paid for: a "purified" draught that still
        # did its Constitution damage when drunk.
        removed = [f"Filter removed {p.source}'s harm: {p.body}."
                   for p in sorted_out.poisons]
        removed += [f"Filter removed {effectspec.render(s)} "
                    f"({s.get('from') or 'the mixture'})."
                    for s in sorted_out.penalties]
        if not removed:
            problems.append(
                "Filter has nothing to hold back: nothing here is harmful. "
                "It strips poisons and penalties, and there are none in this chain.")
        specs = list(sorted_out.benefits)
        drawbacks = []
        effects = effects + removed

    risky = (any(m.risky for m in mats) or bool(volatiles)) and not cleansed

    name = chain.name or _name_for(mats, chain.methods)
    return Result(
        name=name, tier=tier, rank=rank, stages=chain.stages, potency=potency,
        dc=dc, dc_terms=dc_terms, volatiles=volatiles,
        mishap=_mishap(volatiles), risky=risky, cleansed=cleansed,
        effects=effects, drawbacks=drawbacks, specs=specs, removed=removed,
        problems=problems, materials=[m.as_dict() for m in mats],
    )


def _seal_problems(methods: list[str]) -> list[str]:
    """Seal is the finishing method, and a sealed flask is a closed one.

    The order matters beyond "seal last": a chain that seals and *then* reacts has
    closed the vessel before the violence, which is not a craft, it is a grenade with
    extra steps. Named specifically rather than left to the generic finishing rule,
    because "nothing follows it" does not tell the player which two methods to swap.
    """
    if "seal" not in methods or "react" not in methods:
        return []
    if methods.index("seal") < methods.index("react"):
        return ["Nothing reacts inside a sealed flask. React first, seal last."]
    return []


def _react_problems(mats: list[Material], methods: list[str]) -> list[str]:
    """A reaction needs a medium.

    Two dry powders ground together are herbalism's business; a *reaction* happens in
    solution, so the bench wants a solvent — or a herbalism intermediate that pours,
    because a tincture is exactly a prepared liquid medium and the crafts are meant to
    feed each other.
    """
    if "react" not in methods:
        return []
    def pours(m: Material) -> bool:
        if m.kind == "solvent":
            return True
        return m.kind == "intermediate" and "It pours." in m.text
    if any(pours(m) for m in mats):
        return []
    return ["A reaction needs a medium: nothing on the bench is a solvent. "
            "Add one, or start from an intermediate that pours."]


def _volatile_problems(mats: list[Material], volatiles: list[str],
                       methods: list[str]) -> list[str]:
    """The rules volatility imposes before any die is rolled.

    Two volatile materials sharing a vessel is the craft's cardinal sin — one temper
    can be managed, two feed each other — and Stabilize is the method that exists to
    buffer exactly this. A material flagged `needs_stabilizer` attacks its own vessel
    (alkahest, phlogiston) and wants stabilizing even alone.
    """
    out: list[str] = []
    if len(volatiles) >= 2 and "stabilize" not in methods:
        out.append("Two volatile materials in one vessel is an explosion, not a "
                   "preparation. Stabilize the chain, or take one out.")
    for m in mats:
        if m.needs_stabilizer and "stabilize" not in methods:
            out.append(f"{m.name} attacks its own vessel. "
                       f"Stabilize the chain, or lose the flask.")
    return out


def _dc_terms(mats: list[Material], rank: int, stages: int,
              volatile_count: int) -> list[dict]:
    """The DC itemised. Base and per-stage terms are crafting.py's `_dc` rule stated
    the same way (an authored craft_dc beats a derived one; each stage past the first
    adds 2), plus the volatile surcharge that is alchemy's own."""
    stated = [m.craft_dc for m in mats if m.craft_dc is not None]
    base = max(stated) if stated else 5 + 5 * rank
    tier = wc.TIERS[rank - 1]
    terms = [{"label": f"{tier} material" if not stated else "stated craft DC",
              "value": base}]
    extra = max(0, stages - 1)
    if extra:
        terms.append({"label": f"{extra + 1}-stage chain", "value": 2 * extra})
    surplus = max(0, volatile_count - 1)
    if surplus:
        terms.append({"label": f"{volatile_count} volatile materials",
                      "value": VOLATILE_DC_STEP * surplus})
    return terms


def _mishap(volatiles: list[str]) -> str:
    """What a failed roll costs, scaling with how many tempers are in the vessel.

    Written into the preview rather than left for the GM to improvise, for the same
    reason the DC is itemised: the player should be able to read the stakes before
    they commit the material.
    """
    n = len(volatiles)
    if n == 0:
        return ""
    if n == 1:
        return (f"Mishap: {volatiles[0]} spends itself on the bench — the material "
                f"is lost and the alchemist takes its effect at half strength.")
    named = ", ".join(volatiles)
    return (f"Mishap: {named} go up together — every material is lost and the "
            f"alchemist takes the strongest effect at full strength. "
            f"Each volatile past the first raised these stakes.")


def _name_for(mats: list[Material], methods: list[str]) -> str:
    """A working name, so the preview is not headed "Untitled".

    The shape word replaces any shape word already on the end of the lead material's
    name rather than stacking — the "Tincture Tincture Tincture" lesson, learned once
    in crafting.py and not to be re-learned here.
    """
    if not mats:
        return "Empty bench"
    lead = mats[0].name
    for word in sorted(set(SHAPE_WORDS.values()), key=len, reverse=True):
        while lead.lower().endswith(" " + word.lower()):
            lead = lead[: -(len(word) + 1)].rstrip()
    last = methods[-1] if methods else ""
    shape = SHAPE_WORDS.get(last, "Preparation")
    return f"{lead} {shape}".strip()


__all__ = ["TRACK_ID", "Chain", "CraftError", "Material", "Result", "SHAPE_WORDS",
           "POTENCY", "CLEANSING", "FINISHING", "VOLATILE_DC_STEP", "from_dict",
           "get", "load_dir", "materials", "preview"]
