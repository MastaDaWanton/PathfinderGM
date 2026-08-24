"""Leatherworking chains: what a bench of hides and a sequence of methods produces.

The same shape as `rules/crafting.py` on purpose — `TRACK_ID`, `CraftError`, `Chain`,
`preview` returning problems before anything is rolled — so a later dispatcher can treat
"a craft" as one interface with a track behind it, rather than growing an `if herbalism`
per bench. The *semantics* are the tannery's own: herbs steep, hides spoil.

Three physical facts drive every refusal here, and each one is a rule the player learns
once and then knows forever:

  A green hide is meat. It spoils on the same 48-hour clock as any animal part, and
  stitching it sews a bag of rot — cure or tan before anything permanent is done to it.

  Tanning is chemistry, not soaking. It needs a tannin, and the tannin has to be equal
  to the hide: oak bark binds a deer, and dragonhide accepts nothing short of liquor
  quickened with dragon's blood.

  Cuir bouilli is done to *leather*. Raw hide in the hardening kettle boils down to
  glue, so hardening what was never tanned is refused, not weakened.

Rounding follows the crafting module's rule, made precise for the same reason: costs
and penalties round **down**, benefits round **up**. A wearer is never surprised in the
direction that hurts them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import ceil, floor
from pathlib import Path

from . import effectspec
from . import worldclass as wc

TRACK_ID = "leatherworker"

# Methods that change what a piece is worth, as multipliers on its potency — the same
# vocabulary crafting.POTENCY uses, so a dispatcher can read either. Everything else in
# the method list shapes or enables rather than scaling.
POTENCY = {
    "harden": 1.25,     # cuir bouilli: the whole point of the kettle
    "tool": 1.25,       # masterwork finish
    "oil": 1.10,        # dressed leather serves longer and better
}

# The method that has to come last if it is used at all: tooling is the finish, and
# nothing is cut, boiled or dyed after the ornament goes on.
FINISHING = ("tool",)

# Hours before an uncured hide is refuse when the material does not say otherwise.
# The herbalist's animal-part clock (`herbprep.ANIMAL_HOURS`), because a hide *is* an
# animal part; stated here rather than imported so this module reads standalone, and
# pinned equal by the tests so the two cannot drift.
FRESH_HOURS = 48

# Hide sizes, smallest first. Position is what the rules compare, exactly as tier
# position is what `worldclass.TIERS` compares.
SIZES = ("small", "medium", "large", "huge", "gargantuan")


def size_rank(name: str) -> int:
    name = str(name or "medium").strip().lower()
    return SIZES.index(name) + 1 if name in SIZES else 2


# What can be made, what assembles it, and how big a hide it wants. `assembled_by` is
# the method the product cannot exist without — straps are cut work and nothing more,
# everything else is stitched together. `min_size` is why a wolf makes a cloak and not
# barding: the piece has to come out of the hide, and a warhorse does not fit inside a
# wolf.
PRODUCTS: dict[str, dict] = {
    "armour piece": {"assembled_by": "stitch", "min_size": "medium",
                     "word": "Armour"},
    "satchel":      {"assembled_by": "stitch", "min_size": "small", "word": "Satchel"},
    "sheath":       {"assembled_by": "stitch", "min_size": "small", "word": "Sheath"},
    "straps":       {"assembled_by": "cut",    "min_size": "small", "word": "Straps"},
    "barding":      {"assembled_by": "stitch", "min_size": "large", "word": "Barding"},
    "cloak":        {"assembled_by": "stitch", "min_size": "medium", "word": "Cloak"},
    "boots":        {"assembled_by": "stitch", "min_size": "small", "word": "Boots"},
    "bracers":      {"assembled_by": "stitch", "min_size": "small", "word": "Bracers"},
}


class CraftError(ValueError):
    """The chain cannot be described at all. Raised before anything is scored, so a
    chain the character cannot make never advances their track. Merely *bad* chains
    come back as `problems` instead, so the page can grey the button and say why."""


# --- rounding -------------------------------------------------------------------------------

def round_benefit(x: float) -> int:
    """Benefits round up: 80% of a +2 is +2, never a silent +1."""
    return int(ceil(x))


def round_cost(x: float) -> int:
    """Costs round down — toward zero for a penalty, so -1.5 is -1. The character is
    never surprised in the direction that hurts them."""
    return int(floor(x)) if x >= 0 else -int(floor(-x))


def scale_amount(amount: int, potency: float) -> int:
    """A spec's signed amount under the chain's potency, rounded by the rule above."""
    scaled = amount * potency
    return round_benefit(scaled) if amount >= 0 else round_cost(scaled)


# --- materials ------------------------------------------------------------------------------

@dataclass
class Material:
    """One thing on the tannery shelf: a hide, a tannin, a spool, a jar."""
    id: str
    name: str
    kind: str = "hide"          # hide | tannin | thread | oil | dye | wax
                                #  | fitting | treatment
    tier: str = "common"
    craft_dc: int | None = None
    text: str = ""
    risky: bool = False
    # Which creatures this hide comes off, as lowercase name fragments matched against
    # bestiary names — so "skinned a winter wolf" can resolve to an entry here without
    # this module hard-coding 7,000 creature ids.
    from_creatures: list[str] = field(default_factory=list)
    source: str = "bought"      # skinned | foraged | bought | rendered | smithed
    size: str = ""              # hides only; how big a piece can come out of it
    # Hours a raw hide keeps before it is refuse. None for everything that is not a
    # green hide — a jar of dye has no clock.
    fresh_hours: int | None = None
    effects: list = field(default_factory=list)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def is_raw_hide(self) -> bool:
        """On the spoilage clock: a skinned hide that nothing has yet stopped."""
        return self.kind == "hide" and self.fresh_hours is not None

    @property
    def specs(self) -> list[dict]:
        return [dict(e) for e in self.effects]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "craft_dc": self.craft_dc, "text": self.text,
            "risky": self.risky, "from_creatures": self.from_creatures,
            "source": self.source, "size": self.size,
            "fresh_hours": self.fresh_hours, "effects": self.effects,
        }


def from_dict(d: dict) -> Material:
    return Material(
        id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "hide"),
        tier=d.get("tier", "common"), craft_dc=d.get("craft_dc"),
        text=d.get("text", ""), risky=bool(d.get("risky")),
        from_creatures=[str(x).lower() for x in d.get("from_creatures") or []],
        source=d.get("source", "bought"), size=d.get("size", ""),
        fresh_hours=d.get("fresh_hours"),
        effects=list(d.get("effects") or []),
    )


def load_dir(path: str | Path) -> dict[str, Material]:
    """Every material in a directory, accepting both file shapes.

    Both, because two things will write here: this file ships as one list, and the
    homebrew editor writes one file per thing — reading only the first shape is the
    saved-but-never-loaded failure `rules/registry.py` records.
    """
    out: dict[str, Material] = {}
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
            if raw.get("id"):
                m = from_dict(raw)
                out[m.id] = m
    return out


_MATERIALS: dict[str, Material] | None = None


def materials() -> dict[str, Material]:
    """Every material the app knows, shipped and homebrew.

    Homebrew is layered over the shipped set rather than replacing it — the
    `worldclass.tracks()` pattern, for its stated reason: a corrected hide in a later
    build must not be shadowed by a stale copy in the user's data directory, the trap
    CLAUDE.md records from World Bible's stylesheet. A user-dropped hide in
    `homebrew/materials/` just works; a user-dropped copy of a shipped id wins.
    """
    global _MATERIALS
    if _MATERIALS is None:
        from django.conf import settings

        _MATERIALS = load_dir(Path(settings.BASE_DIR) / "content" / "materials")
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
        if user.is_dir():
            _MATERIALS.update(load_dir(user))
    return _MATERIALS


def get(material_id: str) -> Material:
    m = materials().get((material_id or "").strip().lower())
    if m is None:
        raise KeyError(f"no material {material_id!r}")
    return m


def hides_from(creature_name: str) -> list[Material]:
    """The hide entries a fallen creature could yield, by name-fragment match.

    Fragments rather than ids, because the bestiary holds 7,000 names and "wolf" has to
    cover 'adolescent wolf', 'boreal wolf' and next year's homebrew wolf alike. Longest
    fragment wins the sort so 'winter wolf' outranks 'wolf' for a winter wolf.
    """
    said = str(creature_name or "").strip().lower()
    if not said:
        return []
    found = [(max((len(f) for f in m.from_creatures if f in said), default=0), m)
             for m in materials().values() if m.kind == "hide"]
    matched = [(n, m) for n, m in found if n > 0]
    matched.sort(key=lambda pair: -pair[0])
    return [m for _, m in matched]


# --- the chain ------------------------------------------------------------------------------

@dataclass
class Chain:
    """An ordered list of methods applied to a set of materials, aimed at a product.

    `product` is what the bench is trying to make — the pattern on the table — and it
    is part of the chain rather than derived from it, because the same methods make a
    satchel or a sheath and only the pattern knows which.
    """
    methods: list[str] = field(default_factory=list)
    material_ids: list[str] = field(default_factory=list)
    product: str = "satchel"
    name: str = ""

    @property
    def stages(self) -> int:
        return len(self.methods)


@dataclass
class Result:
    """What the chain would make, and everything wrong with attempting it."""
    name: str
    product: str
    tier: str
    rank: int
    stages: int
    potency: float
    dc: int
    risky: bool
    problems: list[str] = field(default_factory=list)
    materials: list[dict] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    specs: list[dict] = field(default_factory=list)
    consumes: dict[str, int] = field(default_factory=dict)
    output: dict | None = None

    def as_dict(self) -> dict:
        return {
            "name": self.name, "product": self.product, "tier": self.tier,
            "rank": self.rank, "stages": self.stages,
            "potency": round(self.potency, 2), "dc": self.dc, "risky": self.risky,
            "problems": self.problems, "materials": self.materials,
            "effects": self.effects, "specs": self.specs,
            "consumes": self.consumes, "output": self.output,
        }


def _stock_entry(stock, mid: str) -> dict:
    """One stock record, normalised. A bare count means "fresh and untreated" — absent
    fields must not invent an age, for the reason `_spoiled_problems` in crafting gives:
    nothing is checked when the caller has no clock to check against."""
    if stock is None:
        return {}
    got = stock.get(mid)
    if got is None:
        return {"count": 0}
    if isinstance(got, dict):
        return dict(got)
    return {"count": int(got)}


def preview(level: int, chain: Chain, stock: dict | None = None) -> Result:
    """What this chain would make, and why it cannot be attempted if it cannot.

    Never raises for a chain that is merely bad — a missing tannin, a method not yet
    learned, a hide beyond the character's tier all come back as `problems` so the page
    can grey the button and say why. `CraftError` is for chains that cannot be
    described at all (an unknown product pattern).

    `stock` is what the character is carrying, as {material id: count} or
    {material id: {"count", "age_hours", "cured", "tanned"}}. Passing None means
    "assume they have it, fresh" — which is what every rules test wants, and the same
    contract `crafting.preview` gives its satchel argument.
    """
    track = wc.get(TRACK_ID)
    level = max(1, min(int(level or 1), track.max_level))
    known = track.unlocked_methods(level)
    ceiling = wc.tier_rank(track.at(level).max_tier)

    product = str(chain.product or "").strip().lower()
    if product not in PRODUCTS:
        raise CraftError(
            f"no product pattern {chain.product!r}. Known: "
            f"{', '.join(sorted(PRODUCTS))}.")
    pattern = PRODUCTS[product]

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
            carrying = int(_stock_entry(stock, mid).get("count", 0))
            if carrying < n:
                name = get(mid).name
                problems.append(
                    f"{name}: you are carrying {carrying}, the chain wants {n}."
                    if carrying else f"You have no {name}.")

    hides = [m for m in items if m.kind == "hide"]
    methods = [str(m).strip().lower() for m in chain.methods]

    # -- what the character knows ----------------------------------------------------------
    every = track.unlocked_methods(track.max_level)
    for m in methods:
        if m not in every:
            problems.append(f"{track.name} has no method called {m!r}.")
        elif m not in known:
            need = next(l.level for l in sorted(track.levels, key=lambda x: x.level)
                        if m in l.methods)
            problems.append(f"{m.title()} is learned at {track.name} {need}.")

    for m in items:
        if m.rank > ceiling:
            problems.append(f"{m.name} is {m.tier}; {track.name} {level} works "
                            f"{track.at(level).max_tier} at best.")

    if not items:
        problems.append("Nothing on the bench.")
    if not methods:
        problems.append("No method chosen.")
    if items and not hides:
        problems.append(
            f"Nothing on the bench wants to become a {product} — there is no "
            f"hide in the pot.")

    for m in methods[:-1]:
        if m in FINISHING:
            problems.append(f"{m.title()} finishes a chain; nothing follows it.")

    # Skinning happens over a carcass. Everything this module hands the bench already
    # carries `source: "skinned"` — the hide is *off* the beast — so `skin` in a bench
    # chain is a category error, and refusing it is what keeps the method meaning the
    # field action it names.
    if "skin" in methods:
        problems.append(
            "The hide is already off the beast — skinning happens in the field, "
            "over a carcass, not at the bench.")

    problems.extend(_spoilage_problems(hides, stock))
    problems.extend(_state_problems(hides, methods, stock, pattern, product))
    problems.extend(_supply_problems(items, hides, methods))
    problems.extend(_size_problems(hides, product, pattern))

    # -- what it makes ---------------------------------------------------------------------
    # As rare as its rarest component, which is also what gates who can make it — the
    # same rule the herbalist's pot uses, because a satchel with one legendary panel in
    # it is legendary work.
    rank = max((m.rank for m in items), default=1)
    tier = wc.TIERS[rank - 1]

    potency = 1.0
    for m in methods:
        potency *= POTENCY.get(m, 1.0)

    risky = any(m.risky for m in items)
    dc = _dc(items, rank, len(methods))

    name = chain.name or _name_for(hides or items, product)
    specs = _gathered_specs(items, potency)
    effects = [f"{s.get('from', '')}: {effectspec.render(s)}".lstrip(": ")
               for s in specs]

    out = {
        "id": _slug(name), "name": name, "kind": "crafted", "craft": TRACK_ID,
        "product": product, "tier": tier, "rank": rank,
        "potency": round(potency, 2), "count": 1,
        "effects": effects, "specs": specs,
        "from_materials": [m.id for m in items],
    }
    return Result(
        name=name, product=product, tier=tier, rank=rank, stages=len(methods),
        potency=potency, dc=dc, risky=risky, problems=problems,
        materials=[m.as_dict() for m in items],
        effects=effects, specs=specs,
        consumes=dict(wanted), output=out,
    )


# --- the refusals ---------------------------------------------------------------------------

def _spoilage_problems(hides, stock) -> list[str]:
    """Any green hide that has outlived its window.

    Refused rather than quietly weakened, exactly as `crafting._spoiled_problems`
    refuses spoiled herbs: a spoiled hide is not worse leather, it is not leather.
    Only checked when the stock entry carries an age — a caller with no clock has
    nothing to check against, and inventing an age would refuse every fresh hide.
    """
    out = []
    for h in hides:
        if not h.is_raw_hide:
            continue
        entry = _stock_entry(stock, h.id)
        if entry.get("cured") or entry.get("tanned"):
            continue
        age = entry.get("age_hours")
        if age is None:
            continue
        window = h.fresh_hours or FRESH_HOURS
        if int(age) >= window:
            out.append(
                f"{h.name} has spoiled — {window} hours is the window for a green "
                f"hide, and this one is {int(age)} hours old. It is refuse. "
                f"Cure what you skin.")
    return out


def _state_problems(hides, methods, stock, pattern, product) -> list[str]:
    """The order the physical states force on the chain.

    Walked as states rather than checked per method, for the reason the herbalist's
    preparation walk gives: what a hide can take next depends on where it already is.
    A hide is green until cured or tanned; a stock entry can say the work was done in
    an earlier session, and then the chain need not repeat it.
    """
    out = []

    def already(flag: str) -> bool:
        # True only when every raw hide on the bench carries the flag — one green hide
        # in a stitched piece rots the whole piece.
        raws = [h for h in hides if h.is_raw_hide]
        return bool(raws) and all(
            _stock_entry(stock, h.id).get(flag) for h in raws)

    raw_present = any(h.is_raw_hide for h in hides) \
        and not (already("cured") or already("tanned"))

    def index(m: str) -> int:
        return methods.index(m) if m in methods else -1

    stitch_at, cure_at, tan_at = index("stitch"), index("cure"), index("tan")
    flense_at, harden_at = index("flense"), index("harden")

    # Stitching a green hide sews a bag of rot. The refusal names the fix, because the
    # rule read once should be known forever.
    if stitch_at >= 0 and raw_present:
        fixed_first = (0 <= cure_at < stitch_at) or (0 <= tan_at < stitch_at)
        if not fixed_first:
            out.append(
                "You cannot stitch an uncured hide — it rots, and the seams go "
                "with it. Cure or tan the hide before anything permanent is done "
                "to it.")

    # Cuir bouilli is done to leather. This is not a tier gate wearing a costume: a
    # level-4 crafter with harden and a green hide still gets refused, because the
    # kettle does not care what level they are.
    if harden_at >= 0:
        tanned_already = already("tanned")
        tanned_in_chain = 0 <= tan_at < harden_at
        if not (tanned_already or tanned_in_chain):
            out.append(
                "You cannot harden what was never tanned — raw hide in the "
                "kettle boils down to glue. Tan it first.")

    # Flesh under the salt putrefies. Flense before the cure or the tan when the hide
    # is still green; a hide flagged cured or tanned was flensed in its own session.
    if raw_present and (cure_at >= 0 or tan_at >= 0):
        first_fix = min(x for x in (cure_at, tan_at) if x >= 0)
        if flense_at < 0 or flense_at > first_fix:
            out.append(
                "Flense before you cure or tan — flesh left on the hide "
                "putrefies in the vat.")

    # The product needs its assembly method: a satchel nobody stitched is a stack of
    # panels, and straps that were never cut are a hide with ambitions.
    verb = pattern["assembled_by"]
    if verb not in methods:
        article = "A" if product[0] not in "aeiou" else "An"
        out.append(f"{article} {product} is {verb} work — put {verb} in the chain.")
    return out


def _supply_problems(items, hides, methods) -> list[str]:
    """Methods that consume a material refuse to run without it.

    Named per method rather than as a generic "missing ingredient", because each one
    teaches the craft: tanning is a chemical argument and the tannin is the argument.
    """
    out = []
    kinds = {m.kind for m in items}

    if "tan" in methods:
        tannins = [m for m in items if m.kind == "tannin"]
        if not tannins:
            out.append("Tan needs a tannin in the pot — oak bark, sumac, "
                       "something to bind the fibres.")
        else:
            # The tannin must be equal to the hide: within one tier, or the liquor
            # cannot bite. This is the ladder that makes dragonblood tannin exist.
            best = max(t.rank for t in tannins)
            for h in hides:
                if h.rank - best > 1:
                    lead = max(tannins, key=lambda t: t.rank)
                    out.append(
                        f"{lead.name} cannot bite {h.name} — the tannin must be "
                        f"within one tier of the hide it is asked to bind.")
    if "stitch" in methods and "thread" not in kinds:
        out.append("Stitching needs thread — sinew, linen, gut. There is none "
                   "in the pot.")
    if "oil" in methods and "oil" not in kinds:
        out.append("Oiling needs an oil in the pot — neatsfoot, currier's tallow, "
                   "something rendered.")
    if "dye" in methods and "dye" not in kinds:
        out.append("Dyeing needs a dye in the pot.")
    if "harden" in methods and "wax" not in kinds:
        out.append("Hardening is done in the wax kettle — put a wax in the pot.")
    if "line" in methods and len(hides) < 2:
        out.append("Lining is two hides working together — an outer hide and an "
                   "inner one. There is only one on the bench.")
    return out


def _size_problems(hides, product: str, pattern) -> list[str]:
    """The piece has to come out of the hide.

    Judged on the largest hide on the bench rather than the sum: patchwork exists, but
    barding that fails at a seam fails under a rider, so the pattern wants one hide big
    enough for the main panels.
    """
    need = size_rank(pattern["min_size"])
    if not hides:
        return []
    biggest = max(hides, key=lambda h: size_rank(h.size))
    if size_rank(biggest.size) >= need:
        return []
    return [f"{biggest.name} is a {biggest.size or 'medium'} hide; {product} wants "
            f"{pattern['min_size']} or better. Bring a bigger beast."]


# --- numbers and names ----------------------------------------------------------------------

def _dc(items, rank: int, stages: int) -> int:
    """Hardest material sets the floor; length of the chain adds to it.

    The same two terms as `crafting._dc`, deliberately: one rule for what a craft DC
    is, whatever the bench. An authored `craft_dc` on a material beats the derived
    number, because an authored number always does.
    """
    stated = [m.craft_dc for m in items if m.craft_dc is not None]
    base = max(stated) if stated else 5 + 5 * rank
    return base + 2 * max(0, stages - 1)


def _gathered_specs(items, potency: float) -> list[dict]:
    """Every material's effects, marked with their source and scaled by the chain.

    Deduplicated on (source, spec) so two panels of the same hide grant its bonus
    once, while two *different* hides that both aid Stealth keep both lines — two
    materials doing the same thing is a fact the card should keep.

    Scaling touches only signed `amount` fields, through the rounding rule, and only
    when the chain earned a multiplier. Dice, DCs and narrative text are never scaled:
    inventing "1.25 × 1d6" would be a guess wearing a number.
    """
    out: list[dict] = []
    seen: set[str] = set()
    for m in items:
        for spec in m.specs:
            marked = {**spec, "from": spec.get("from") or m.name}
            if potency != 1.0 and isinstance(marked.get("amount"), int) \
                    and marked.get("type") != "resistance":
                # Resistance ratings are the book's own numbers (dragonhide resists 5
                # because the book says 5); scaling them would un-book the book.
                marked["amount"] = scale_amount(marked["amount"], potency)
            key = repr(sorted(marked.items(), key=lambda kv: str(kv[0])))
            if key not in seen:
                seen.add(key)
                out.append(marked)
    return out


def _name_for(items, product: str) -> str:
    """A working name, so the preview is not headed "Untitled".

    The lead hide's name, with the material words stripped so "Winter Wolf Pelt" makes
    a "Winter Wolf Cloak" and not a "Winter Wolf Pelt Cloak" — the naming lesson
    `crafting._name_for` learned ten tinctures deep, applied before the first
    compounding name ever ships.
    """
    if not items:
        return f"Empty-bench {PRODUCTS[product]['word']}"
    lead = items[0].name
    for word in ("Hide", "Pelt", "Skin", "Leather", "Plate", "Shell"):
        if lead.endswith(" " + word):
            lead = lead[: -(len(word) + 1)]
            break
    return f"{lead} {PRODUCTS[product]['word']}".strip()


def _slug(name: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug
