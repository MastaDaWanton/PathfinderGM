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
from .tables import ARMOUR
from pathfindergm import files

TRACK_ID = "leatherworker"

# One glyph per material kind, for the shelf. A hide must never render as a herb — that
# was the reported bug, and it happened because the shelf had one icon for "content".
# Herbalism owns 🌿 herb, 🍄 fungus, 🦴 monster part, ☠️ poison; none is reused here, and
# the bench asserts across all five crafts that no two maps collide.
KIND_GLYPH: dict[str, str] = {
    "hide": "🦬",        # the beast it came off
    "tannin": "🛢️",      # the bark vat
    "thread": "🧵",
    "oil": "🧴",
    "dye": "🎨",
    "wax": "🕯️",
    "fitting": "🔘",     # a stud, a buckle — the smith's contribution
    # The reserved pool held no vessel, salt or chemical glyph, so the least-wrong
    # symbol wins: a bundle tied for the liming pit. Flagged for reassignment if a
    # better one frees up — it is the only entry here chosen by elimination.
    "treatment": "🪢",
}

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
#
# `slot` is the body slot the finished piece occupies, in the engine's own vocabulary. A
# satchel and a sheath are *carried*, not worn, so their slot is None and `wearable` is
# false — a bag that occupied the shoulders slot would fight a cloak for it.
#
# `armour` marks the patterns that can come off the bench as armour proper. The key
# itself is worked out per chain (see `_armour_key`), because whether a piece is leather
# or studded leather depends on what was on the bench, not on the pattern alone.
PRODUCTS: dict[str, dict] = {
    "armour piece": {"assembled_by": "stitch", "min_size": "medium",
                     "word": "Armour", "slot": "armor", "wearable": True,
                     "armour": True},
    "barding":      {"assembled_by": "stitch", "min_size": "large", "word": "Barding",
                     # Worn, but by a mount — it occupies no slot on the character
                     # sheet, and claiming `armor` would have the rider wearing it.
                     "slot": None, "wearable": True, "armour": True},
    "cloak":        {"assembled_by": "stitch", "min_size": "medium", "word": "Cloak",
                     "slot": "shoulders", "wearable": True},
    "boots":        {"assembled_by": "stitch", "min_size": "small", "word": "Boots",
                     "slot": "feet", "wearable": True},
    "bracers":      {"assembled_by": "stitch", "min_size": "small", "word": "Bracers",
                     "slot": "wrists", "wearable": True},
    "gloves":       {"assembled_by": "stitch", "min_size": "small", "word": "Gloves",
                     "slot": "hands", "wearable": True},
    "belt":         {"assembled_by": "stitch", "min_size": "small", "word": "Belt",
                     "slot": "belt", "wearable": True},
    "cap":          {"assembled_by": "stitch", "min_size": "small", "word": "Cap",
                     "slot": "head", "wearable": True},
    "satchel":      {"assembled_by": "stitch", "min_size": "small", "word": "Satchel",
                     "slot": None, "wearable": False},
    "sheath":       {"assembled_by": "stitch", "min_size": "small", "word": "Sheath",
                     "slot": None, "wearable": False},
    "straps":       {"assembled_by": "cut",    "min_size": "small", "word": "Straps",
                     "slot": None, "wearable": False},
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
    # How it is come by, which is what the play page's acquisition hub turns into an
    # excursion: harvested off a carcass, gathered where it grows, mined out of the
    # ground, or bought. `source` is the older, finer word for the same idea (rendered,
    # smithed) and is kept because it carries the blacksmith join; `obtain` is the one
    # the hub dispatches on.
    obtain: str = "bought"      # harvested | gathered | mined | bought
    price_gp: float | None = None   # bought only
    biomes: list[str] = field(default_factory=list)  # gathered and mined only

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
            "obtain": self.obtain, "price_gp": self.price_gp,
            "biomes": self.biomes, "glyph": self.glyph,
        }

    @property
    def glyph(self) -> str:
        """The shelf icon. Unknown kinds fall back to the hide glyph rather than to a
        herb: a homebrew material with a novel kind is still tannery goods."""
        return KIND_GLYPH.get(self.kind, KIND_GLYPH["hide"])


def from_dict(d: dict) -> Material:
    return Material(
        id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "hide"),
        tier=d.get("tier", "common"), craft_dc=d.get("craft_dc"),
        text=d.get("text", ""), risky=bool(d.get("risky")),
        from_creatures=[str(x).lower() for x in d.get("from_creatures") or []],
        source=d.get("source", "bought"), size=d.get("size", ""),
        fresh_hours=d.get("fresh_hours"),
        effects=list(d.get("effects") or []),
        # A homebrew entry that says nothing is bought: the safest default, because a
        # material wrongly marked harvested would appear on every carcass in the game.
        obtain=str(d.get("obtain") or "bought").strip().lower(),
        price_gp=d.get("price_gp"),
        biomes=[str(b).strip().lower() for b in d.get("biomes") or []],
    )


def load_dir(path: str | Path, claimed_by: str = "") -> dict[str, Material]:
    """Every material in a directory, accepting both file shapes.

    Both, because two things write here: this file ships as one list, and the homebrew
    editor writes one file per thing — reading only the first shape is the
    saved-but-never-loaded failure `rules/registry.py` records.

    `claimed_by` filters to one craft's goods. `content/materials/` is **one shelf for
    all five benches**, so without it this loader answered with the blacksmith's ash
    hafts and living steel: measured, `obtainable("gathered", biome="forest")` came
    back with six blacksmith entries out of eleven. Worse than a cluttered list — an
    inert haft in a leatherworking chain still raised the result's tier and DC, because
    the rank rule reads the rarest thing on the bench.

    Ownership is claimed by the file (`"craft": "leatherworker"` at top level) and may
    be overridden per entry; a file *named* for the craft counts as claiming it, so
    losing the key cannot silently empty the shelf. With `claimed_by` set, an entry
    must claim the craft to be kept — "keep whatever claims nobody" was the first
    version and it kept all four sibling files, because none of them tags itself.

    `claimed_by` is left empty for the homebrew directory, where everything is kept: a
    material a person put in their own directory is one they meant for a bench, and
    dropping it for a missing tag would be the silent-drop failure `rules/registry.py`
    records.
    """
    out: dict[str, Material] = {}
    p = Path(path)
    if not p.is_dir():
        return out
    for file in sorted(p.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except Exception as exc:
            files.unreadable(file, exc)
            continue
        file_craft = str(data.get("craft") or "").strip().lower() \
            if isinstance(data, dict) else ""
        if not file_craft and claimed_by and file.stem.startswith(claimed_by):
            file_craft = claimed_by
        entries = data.get("materials") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            entries = [data] if isinstance(data, dict) and data.get("id") else []
        for raw in entries:
            if not raw.get("id"):
                continue
            craft = str(raw.get("craft") or file_craft or "").strip().lower()
            if claimed_by and craft != claimed_by:
                continue
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

        shelf = Path(settings.BASE_DIR) / "content" / "materials"
        _MATERIALS = load_dir(shelf, claimed_by=TRACK_ID)
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
        if user.is_dir():
            # Homebrew is not filtered by craft: a material a person put in their own
            # directory is one they meant for a bench, and refusing it for a missing
            # tag would be the silent drop this project has already paid for once.
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
    return _by_creature(creature_name, lambda m: m.kind == "hide")


def _by_creature(creature_name: str, keep) -> list[Material]:
    """Materials whose `from_creatures` fragments appear in this creature's name.

    Longest fragment first, so 'winter wolf' outranks 'wolf' for a winter wolf and the
    bench offers the specific pelt before the generic one.
    """
    said = str(creature_name or "").strip().lower()
    if not said:
        return []
    found = [(max((len(f) for f in m.from_creatures if f in said), default=0), m)
             for m in materials().values() if keep(m)]
    matched = [(n, m) for n, m in found if n > 0]
    matched.sort(key=lambda pair: -pair[0])
    return [m for _, m in matched]


# --- acquisition ----------------------------------------------------------------------------
#
# The play page's craft-action button is the single hub for *obtaining* material, and this
# is the track's half of it: the data, not the UI. Each excursion says which `obtain` kind
# it serves and what the scene has to provide before it can be offered at all.
#
# Skinning is the flagship: it is the only one that turns a fight into stock, and it is
# why `hides_from` exists.

ACQUISITION: dict[str, dict] = {
    "skin": {
        "id": "skin", "label": "Skin the carcass", "obtain": "harvested",
        "requires": "creature",
        "requires_note": "A fallen creature in the scene. What it yields is read off "
                         "its name, so the beast decides the hide.",
        "method": "skin",
        "blurb": "Take the hide, and the sinew and tallow with it. The spoilage "
                 "clock starts now — 48 hours to cure or tan.",
    },
    "gather": {
        "id": "gather", "label": "Strip bark and gather", "obtain": "gathered",
        "requires": "biome",
        "requires_note": "Somewhere that grows it. Oak bark wants forest, mangrove "
                         "wants the salt coast, glowcap wants the deep places.",
        "blurb": "Tannins, plant dyes, pitch and wax — the vat's supplies come out "
                 "of the landscape, not a shop.",
    },
    "mine": {
        "id": "mine", "label": "Dig for salt and mineral", "obtain": "mined",
        "requires": "biome",
        "requires_note": "Underground, mountain or hardpan, depending on the mineral.",
        "blurb": "Curing salt, alum, quicklime and the mineral colours.",
    },
    "buy": {
        "id": "buy", "label": "Buy from the market", "obtain": "bought",
        "requires": "market",
        "requires_note": "A settlement that trades. Everything bought carries a "
                         "price in gp; nothing here is free.",
        "blurb": "Thread, buckles and studs off the smith's bench, and the "
                 "imported colours.",
    },
}


def obtainable(obtain_kind: str, *, biome=None, creature=None) -> list[Material]:
    """What this excursion could actually turn up, here, now.

    Harvesting delegates to the creature: a winter wolf yields its own pelt, plus the
    goods any carcass yields (sinew, gut, tallow). It never yields another beast's
    hide, which is the whole point of asking the scene rather than listing the shelf —
    without the creature filter, skinning a deer offered dragonhide.

    Gathering and mining ask the ground. Buying asks nothing but a market, so it
    answers with everything that has a price.
    """
    kind = str(obtain_kind or "").strip().lower()
    pool = [m for m in materials().values() if m.obtain == kind]

    if kind == "harvested":
        if not creature:
            # No carcass named: nothing to skin. An empty list, not the whole shelf —
            # offering every hide in the game with no beast in the scene is how the
            # old foraging panel handed out material for free.
            return []
        specific = _by_creature(creature, lambda m: m.obtain == "harvested")
        # What any carcass yields: harvested goods that name no creature at all.
        generic = [m for m in pool if not m.from_creatures]
        seen, out = set(), []
        for m in specific + generic:
            if m.id not in seen:
                seen.add(m.id)
                out.append(m)
        return out

    if kind in ("gathered", "mined"):
        if not biome:
            return sorted(pool, key=lambda m: m.name)
        here = str(biome).strip().lower()
        return sorted((m for m in pool if here in m.biomes), key=lambda m: m.name)

    return sorted(pool, key=lambda m: (m.price_gp or 0, m.name))


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


def chain_from_body(body: dict) -> Chain:
    """The bench's POST JSON as a Chain.

    Tolerant on purpose: a missing key is an empty chain, not a 500. The bench posts
    partial bodies constantly — the preview fires on every click, including the first
    one, when nothing has been chosen yet — and `preview` already answers an empty
    chain with readable problems ("Nothing on the bench", "No method chosen"). Raising
    here would replace those sentences with a stack trace.

    Both spellings of each key are accepted (`materials`/`material_ids`,
    `product`/`pattern`) because the five benches are being written in parallel and a
    dispatcher that has to remember which craft calls it which is a bug waiting to be
    filed.
    """
    body = body or {}
    methods = [str(m).strip().lower()
               for m in (body.get("methods") or []) if str(m).strip()]
    raw_materials = body.get("materials")
    if raw_materials is None:
        raw_materials = body.get("material_ids") or []
    material_ids = [str(m).strip().lower()
                    for m in raw_materials if str(m).strip()]
    product = str(body.get("product") or body.get("pattern") or "satchel") \
        .strip().lower()
    return Chain(methods=methods, material_ids=material_ids, product=product,
                 name=str(body.get("name") or "").strip())


def stock_from_body(body: dict) -> dict:
    """The carried stock out of the same POST body.

    Kept off the Chain deliberately: stock is what the character happens to own, and a
    chain is the recipe. Putting inventory inside the recipe would mean two identical
    chains were unequal because one crafter was richer. The bench calls both.
    """
    stock = (body or {}).get("stock") or {}
    if not isinstance(stock, dict):
        return {}
    out: dict[str, object] = {}
    for key, value in stock.items():
        mid = str(key).strip().lower()
        if isinstance(value, dict):
            out[mid] = dict(value)
        else:
            try:
                out[mid] = int(value)
            except (TypeError, ValueError):
                continue
    return out


# --- the crafter's own bonus ------------------------------------------------------------

def check_terms(actor, level: int) -> list[dict]:
    """What a leatherworker adds to the die, itemised.

    **d20 + track level + half character level + Intelligence.** The same three terms
    `crafting.check_terms` uses, with Int in the ability slot because Craft is an
    Int-based skill in PF1e — herbalism reads Wisdom for its own authored reason, and
    copying that here would have made the tannery a wisdom craft by accident.

    Itemised rather than summed because the sum is the boring half: "+9" says nothing,
    "Leatherworker 4, half level +3, Int +2" says which of the three to go and improve.
    """
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor else 1
    intelligence = int(actor.ability_mod("int")) if actor is not None else 0
    return [
        {"label": f"Leatherworker {track_level}", "value": track_level},
        # Half level, rounded down, as every half-level term in 1e rounds.
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intelligence},
    ]


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


def _chance(dc: int, bonus: int, problems=()) -> int:
    """Percent chance the check makes the DC, for the label on the button.

    Clamped to 5-95 exactly as `crafting._chance` clamps it: a natural 1 always fails
    and a natural 20 always succeeds, so no craft is ever certain either way and the
    number must not claim otherwise. A chain with problems is 0 — it is not attempted.
    """
    if problems:
        return 0
    need = dc - bonus
    return max(5, min(95, int(round(100 * (21 - need) / 20))))


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
    # The crafter's own bonus on this chain and what it is made of, plus what that
    # comes to as a percentage. Zero and empty when no actor was supplied, which is
    # every rules-level call — the numbers are a property of the crafter, not the chain.
    bonus: int = 0
    terms: list[dict] = field(default_factory=list)
    chance: int = 0

    def as_dict(self) -> dict:
        return {
            "name": self.name, "product": self.product, "tier": self.tier,
            "rank": self.rank, "stages": self.stages,
            "potency": round(self.potency, 2), "dc": self.dc, "risky": self.risky,
            "problems": self.problems, "materials": self.materials,
            "effects": self.effects, "specs": self.specs,
            "consumes": self.consumes, "output": self.output,
            "bonus": self.bonus, "terms": self.terms, "chance": self.chance,
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


def preview(level: int, chain: Chain, stock: dict | None = None,
            actor=None) -> Result:
    """What this chain would make, and why it cannot be attempted if it cannot.

    Never raises for a chain that is merely bad — a missing tannin, a method not yet
    learned, a hide beyond the character's tier all come back as `problems` so the page
    can grey the button and say why. `CraftError` is for chains that cannot be
    described at all (an unknown product pattern).

    `stock` is what the character is carrying, as {material id: count} or
    {material id: {"count", "age_hours", "cured", "tanned"}}. Passing None means
    "assume they have it, fresh" — which is what every rules test wants, and the same
    contract `crafting.preview` gives its satchel argument.

    `actor` is the crafter, and it is optional for the same reason: with one, the
    result carries `bonus`, `terms` and `chance`; without one it carries zeroes and
    every rule above still answers. The chain's legality is never a question about who
    is standing at the bench.
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

    out = _output(name, product, pattern, tier, rank, potency, methods, items,
                  hides, stock, effects, specs)
    terms = check_terms(actor, level) if actor is not None else []
    bonus = sum(t["value"] for t in terms)
    return Result(
        name=name, product=product, tier=tier, rank=rank, stages=len(methods),
        potency=potency, dc=dc, risky=risky, problems=problems,
        materials=[m.as_dict() for m in items],
        effects=effects, specs=specs,
        consumes=dict(wanted), output=out,
        bonus=bonus, terms=terms,
        chance=_chance(dc, bonus, problems) if actor is not None else 0,
    )


# --- the output contract ---------------------------------------------------------------

def _is_tanned(hides, methods, stock) -> bool:
    """Whether the piece is leather rather than cured rawhide.

    Either the chain tans it, or every raw hide on the bench was tanned in an earlier
    session. A hide that is not a raw hide at all (nothing on the shelf spoils) counts
    as ready — those entries are already-worked stock.
    """
    if "tan" in methods:
        return True
    raws = [h for h in hides if h.is_raw_hide]
    if not raws:
        return bool(hides)
    return all(_stock_entry(stock, h.id).get("tanned") for h in raws)


def _armour_key(product: str, pattern: dict, items, tanned: bool) -> str | None:
    """Which row of `tables.ARMOUR` this piece is, if it is armour at all.

    Read off the bench rather than the pattern: studs are what turn leather armour into
    studded leather, and studs are a fitting somebody either put on the bench or did
    not. Returned as a key that is **verified to exist in the table**, because a key the
    sheet has never heard of would equip as nothing and report no error — the silent
    failure this project keeps paying for.

    Untanned work is not armour: cured rawhide is a garment, and PF1e's leather armour
    is leather. The piece is still craftable; it simply carries no armour row.
    """
    if not pattern.get("armour") or not tanned:
        return None
    studded = any(m.kind == "fitting" and "stud" in f"{m.id} {m.name}".lower()
                  for m in items)
    key = "studded leather" if studded else "leather"
    return key if key in ARMOUR else None


def _output(name, product, pattern, tier, rank, potency, methods, items, hides,
            stock, effects, specs) -> dict:
    """The finished piece as the rest of the app has to see it.

    **Masterwork is the headline.** `tool` is the masterwork finish, and until this
    field existed nothing downstream could tell a tooled breastplate from a plain one —
    which matters now that the enchanter requires a masterwork vessel and armour is one
    of the item classes it will accept. It is read off the chain, not off the tier: a
    legendary hide badly finished is still not masterwork, and a common hide tooled by
    a master is.
    """
    tanned = _is_tanned(hides, methods, stock)
    armour = _armour_key(product, pattern, items, tanned)
    wearable = bool(pattern.get("wearable"))
    return {
        "id": _slug(name), "name": name, "kind": "crafted", "craft": TRACK_ID,
        "product": product, "tier": tier, "rank": rank,
        "potency": round(potency, 2), "count": 1,
        "effects": effects, "specs": specs,
        "from_materials": [m.id for m in items],
        "masterwork": "tool" in methods,
        "tanned": tanned,
        "armour": armour,
        "slot": pattern.get("slot"),
        "wearable": wearable,
        # Nothing the tannery makes is spent by using it — a cloak is worn, not drunk.
        # Said explicitly so the bench does not have to infer it from the absence of a
        # dose, which is how a satchel would end up with a Drink button.
        "usable": False,
        "how": ["wear"] if wearable else (["carry"] if items else []),
    }


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
