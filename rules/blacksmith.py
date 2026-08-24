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

# One glyph per kind in the catalogue, for the shelf and the chain builder. Distinct
# within the track and distinct across all five crafts — herbalism owns the plant and
# carcass symbols, so nothing here reuses them. Picked from the forge's own vocabulary
# so a player reading a mixed shelf can tell a fuel from a flux without reading a word.
KIND_GLYPH: dict[str, str] = {
    "ore": "⛏️",         # what you dig
    "metal": "🪨",        # what it smelts to
    "alloy": "⚙️",        # two metals answering to each other
    "fuel": "🔥",         # what feeds the fire
    "flux": "🧱",         # what cleans the melt
    "quenchant": "💧",    # the bath
    "fitting": "🔩",      # what gets riveted on
    "treatment": "🛠️",    # what is done to the finished surface
}


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
    # How a character comes by it. `source` is the older, prose-ish field and is kept
    # because the shelf and the book both read it; `obtain` is the shared vocabulary the
    # acquisition excursions dispatch on — mined | bought | harvested | gathered.
    obtain: str = ""
    price_gp: float | None = None
    # Creature-name fragments, matched as substrings the way the leatherworker matches
    # its hides: "dragon" catches a red dragon, and a wyvern needs its own fragment.
    from_creatures: list[str] = field(default_factory=list)
    # Which shipped file this came out of, as a filename stem. `content/materials` is
    # one shelf shared by all five crafts, and `kind` cannot tell them apart —
    # "treatment" appears in all four shipped catalogues and "fitting" in two. Empty
    # means homebrew, which belongs to no shipped file and so shows everywhere, exactly
    # as the shelf's own commit settled it.
    catalogue: str = ""

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
            "weight_factor": self.weight_factor, "glyph": self.glyph,
            "obtain": self.obtain, "price_gp": self.price_gp,
            "from_creatures": self.from_creatures,
        }

    @property
    def glyph(self) -> str:
        return KIND_GLYPH.get(self.kind, "🪨")


# The old `source` words mapped onto the shared `obtain` vocabulary, for any entry
# written before `obtain` existed — a homebrew metal dropped in with only `source` still
# lands in the right excursion instead of silently belonging to none.
_OBTAIN_FROM_SOURCE = {"mined": "mined", "bought": "bought",
                       "monster": "harvested", "harvested": "gathered"}


def from_dict(d: dict) -> Material:
    source = d.get("source", "bought")
    # Two shapes of `obtain` exist on the shared shelf: this track writes a flat word
    # beside `price_gp`/`from_creatures`/`biomes`, and a sibling writes a nested
    # {"how": ..., "market": ..., "price_gp": ...}. Both are read rather than one being
    # declared correct, because the shelf is shared and a loader that understands only
    # its own dialect silently drops every neighbour's acquisition data.
    raw_obtain = d.get("obtain")
    nested = raw_obtain if isinstance(raw_obtain, dict) else {}
    obtain = str(nested.get("how") or (raw_obtain if isinstance(raw_obtain, str) else "")
                 or _OBTAIN_FROM_SOURCE.get(source, "bought"))
    price = d.get("price_gp", nested.get("price_gp"))
    creatures = d.get("from_creatures") or nested.get("from_creatures") or []
    biomes = d.get("biomes") or nested.get("biomes") or []
    return Material(
        id=d["id"], name=d["name"], kind=d.get("kind", "metal"),
        tier=d.get("tier", "common"), craft_dc=d.get("craft_dc"),
        text=d.get("text", ""), risky=bool(d.get("risky")),
        source=source,
        biomes=list(biomes),
        effects=list(d.get("effects") or []),
        effects_converted=bool(d.get("effects_converted")),
        weight_factor=float(d.get("weight_factor", 1.0)),
        obtain=obtain,
        price_gp=price,
        from_creatures=[str(x).lower() for x in creatures],
        catalogue=str(d.get("catalogue") or ""),
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
                # Stamped with the file it came from, because the folder is one shelf
                # shared by five crafts and nothing else in the entry says whose it is.
                out[str(raw["id"]).strip().lower()] = {**raw, "catalogue": file.stem}
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
                # Homebrew is attributable to no shipped catalogue, so it belongs to
                # every bench rather than none — unless it is correcting a shipped
                # entry, which keeps the catalogue it is correcting.
                merged["catalogue"] = raw.get(key, {}).get("catalogue", "")
                raw[key] = merged
        _MATERIALS = {k: from_dict({**v, "id": k}) for k, v in raw.items()}
    return _MATERIALS


def get(material_id: str) -> Material:
    m = materials().get((material_id or "").strip().lower())
    if m is None:
        raise KeyError(f"no material {material_id!r}")
    return m


# The shipped file this track's own materials live in. `content/materials` is one shelf
# for five crafts, so "everything on the shelf" and "everything a smith works with" are
# different questions and only one of them is this track's.
CATALOGUE = "blacksmith-materials"


def mine() -> dict[str, Material]:
    """This track's own shelf: what shipped in the blacksmith catalogue, plus homebrew.

    `materials()` deliberately stays shelf-wide — a smith may rivet a leatherworker's
    grip onto a blade, and a chain naming one must resolve it. This is the narrower
    question the bench and the excursions ask: what is *ours* to list and to go and
    find. Without the split, prospecting for ore turned up wyvern hide.
    """
    return {k: m for k, m in materials().items()
            if m.catalogue in (CATALOGUE, "")}


# --- acquisition -----------------------------------------------------------------------
#
# The craft-action button is the one hub for *obtaining* material, replacing the foraging
# panel that used to live inside the crafting menu. A track supplies the data — which
# excursions it offers and what each could turn up here — and the page supplies the UI.
#
# Mining is the flagship and the reason `biomes` was populated on every ore in the first
# place: a smith standing in mountains prospects and comes back with mountain ore, the
# same way foraging answers to the ground underfoot.
ACQUISITION: dict[str, dict] = {
    "prospect": {
        "id": "prospect",
        "label": "Prospect for ore",
        "obtain": "mined",
        "requires": "biome",
        "verb": "prospecting",
        "blurb": "Read the rock for colour and float, and dig where it promises. What "
                 "the ground holds is what the ground is: no seam of sea-salt in a "
                 "mountain, and no skymetal in a ploughed field.",
    },
    "buy": {
        "id": "buy",
        "label": "Buy from the market",
        "obtain": "bought",
        "requires": "market",
        "verb": "buying",
        "blurb": "Bar stock from the ironmonger, charcoal from the collier, fittings "
                 "from the joiner. Anything with a price and a settlement to pay it in.",
    },
    "salvage": {
        "id": "salvage",
        "label": "Harvest from a carcass",
        "obtain": "harvested",
        "requires": "carcass",
        "verb": "harvesting",
        "blurb": "Blood, bone, hide and stranger things, taken off what was killed. "
                 "What can be had depends entirely on what is lying there.",
    },
    "gather": {
        "id": "gather",
        "label": "Gather from the land",
        "obtain": "gathered",
        "requires": "biome",
        "verb": "gathering",
        "blurb": "Peat from the bog, brine from the tideline, a straight ash pole from "
                 "the wood. The materials the land gives up without a shaft sunk.",
    },
}


def obtainable(obtain_kind: str, *, biome: str | None = None,
               creature: str | None = None) -> list[Material]:
    """What one excursion could actually turn up, here, given this ground or this corpse.

    Filtered rather than ranked: this answers "what is possible", and which of them the
    character actually finds is a roll the excursion makes, not a question the catalogue
    can settle.

    A material with no biomes listed is available on any ground — water is water
    wherever you are standing — and that is deliberately not the same as a material
    listing biomes that exclude here. "Empty is not the same as absent" applies to
    ground as much as to form fields.

    A creature is matched on name fragments, longest first, the way the leatherworker
    matches hides: "young red dragon" must find the dragon entries without a bestiary
    lookup, because the GM types what they killed rather than an id.
    """
    kind = (obtain_kind or "").strip().lower()
    out = [m for m in mine().values() if m.obtain == kind]

    if biome:
        want = str(biome).strip().lower()
        out = [m for m in out if not m.biomes or want in m.biomes]
    if creature:
        said = str(creature).strip().lower()
        out = [m for m in out
               if any(frag in said for frag in m.from_creatures)]
    elif kind == "harvested":
        # No carcass named means no harvest: every harvested entry is off something
        # specific, and returning all of them would let a player skin thin air.
        out = []
    return sorted(out, key=lambda m: (m.rank, m.name))


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


def chain_from_body(body: dict) -> Chain:
    """The bench's POST JSON as a Chain.

    Tolerant by design: a missing key is an empty chain, not an error, because this is
    the first thing that touches user input and `preview` is already the place that says
    what is wrong with a chain in sentences. A parser that raises here would turn "you
    have not chosen a method yet" into a 500.

    `base` is accepted under three names because three things can send it — the chain
    builder posts `base`, an item page posts `item`, and the weapons picker posts
    `weapon`. Reading only one of them is the shape of bug that makes a form submit
    silently do nothing.
    """
    body = body if isinstance(body, dict) else {}

    def _list(key: str) -> list[str]:
        value = body.get(key)
        if isinstance(value, str):
            # A comma-joined string is what a plain HTML form sends when JavaScript is
            # off, and dropping it would make the bench work only with scripting.
            return [p.strip() for p in value.split(",") if p.strip()]
        if isinstance(value, (list, tuple)):
            return [str(p).strip() for p in value if str(p).strip()]
        return []

    base = ""
    for key in ("base", "item", "weapon", "armour"):
        if str(body.get(key) or "").strip():
            base = str(body[key]).strip()
            break

    return Chain(
        track=TRACK_ID,
        methods=_list("methods"),
        material_ids=_list("materials") or _list("material_ids"),
        base=base,
        name=str(body.get("name") or "").strip(),
    )


def stock_from_body(body: dict) -> dict[str, int]:
    """What the bench says the smith is carrying, as {material id: count}.

    Separate from the chain because it is a fact about the character rather than about
    the work, and `preview` takes it separately for the same reason: passing None means
    "assume they have it", which every rules test wants and no live bench does.
    """
    raw = (body or {}).get("stock")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        try:
            n = int(value)
        except (TypeError, ValueError):
            continue
        if n > 0:
            out[str(key).strip().lower()] = n
    return out


# The quality ladder, decided by which methods the chain contains. Masterwork is the
# book's own rule made procedural: Craft says a masterwork component is its own DC-20
# piece of work, and here that work is named — the steel must be tempered and the
# working surface finished. Fine is the honest step between: one of the two, not both.
#
# The shaping methods (fold, draw) were originally required for masterwork as well, and
# that was measured to be a dead end. `rules/enchanter.py` gates every binding on a
# masterwork vessel at Enchanter *1* — "Commission one from the smith" — while fold and
# draw are Blacksmith 4, so the whole enchanting economy sat behind 140 MP of a track
# the enchanter may never have taken. Masterwork is professional work in 1e, not
# legendary work: DC 20, purchasable in any city. It belongs where the professional
# methods are, which is Blacksmith 3. Fold and draw stay at 4 as what they always
# were — pattern-welding and wire-drawing, which make named steels and mail, not
# quality on their own.
MASTERWORK_DC = 20

SHAPING = ("fold", "draw")
FINISHING_QUALITY = ("hone", "polish")


def quality_of(methods: list[str]) -> str:
    tempered = "temper" in methods
    finished = any(m in FINISHING_QUALITY for m in methods)
    if tempered and finished:
        return "masterwork"
    if tempered or finished:
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
    # What the successful craft puts in the player's pack. The whole point of the
    # contract: a forged sword that cannot be wielded is a paragraph, which is what
    # every crafted item was before `specs` reached the engine.
    output: dict | None = None
    # The crafter's own bonus on this chain and what it is made of. Empty when no actor
    # was supplied — the rules tests ask what a chain *is*, not who is attempting it.
    bonus: int = 0
    terms: list[dict] = field(default_factory=list)
    chance: int = 0

    def as_dict(self) -> dict:
        return {
            "name": self.name, "tier": self.tier, "rank": self.rank,
            "quality": self.quality, "stages": self.stages, "dc": self.dc,
            "risky": self.risky, "weight_lb": self.weight_lb, "base": self.base,
            "effects": self.effects, "specs": self.specs, "removed": self.removed,
            "problems": self.problems, "consumes": self.consumes,
            "output": self.output, "bonus": self.bonus, "terms": self.terms,
            "chance": self.chance,
        }


# Which body slot a finished piece occupies, by what it is. `tables.SLOTS` owns the
# vocabulary; these are the three a forge can fill.
def _slot_for(base: dict | None) -> str | None:
    if not base:
        return None
    if base.get("family") == "armour":
        return "armor"
    if base.get("family") == "weapon":
        return "shield" if "shield" in str(base.get("id", "")) else "hands"
    return None


def _slug(text: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in str(text).lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out


def _output(name: str, tier: str, rank: int, quality: str, base: dict | None,
            effects: list[str], specs: list[dict], materials_used: list[str],
            weight_lb: int | None) -> dict:
    """The finished piece as an inventory item.

    Shaped so the pack, the equip screen and the engine can all read it without knowing
    which craft made it: `kind: "crafted"` and `craft` say where it came from, `weapon`
    and `armour` point back at the real tables so it can actually be wielded or worn,
    and `specs` are the validated effects the engine already knows how to apply.

    `masterwork` is surfaced as its own boolean rather than left implicit in `quality`,
    because it is the fact another track asks about: the enchanter refuses a vessel that
    does not assert it, and reading a quality string from a sibling module would be a
    second copy of this rule waiting to drift.
    """
    slot = _slot_for(base)
    family = (base or {}).get("family")
    return {
        "id": _slug(name), "name": name, "kind": "crafted", "craft": TRACK_ID,
        "tier": tier, "rank": rank, "count": 1,
        "effects": list(effects), "specs": [dict(s) for s in specs],
        "from_materials": list(materials_used),
        "masterwork": quality == "masterwork",
        "quality": quality,
        "weight_lb": weight_lb,
        "weapon": (base or {}).get("id") if family == "weapon" else None,
        "armour": (base or {}).get("id") if family == "armour" else None,
        "slot": slot,
        "wearable": slot is not None,
        # A forged piece is equipment, not a consumable: nothing is drunk or thrown, so
        # `usable` is false and `how` is empty. Both are stated rather than omitted, so
        # a pack rendering every craft's output does not have to special-case this one.
        "usable": False,
        "how": [],
    }


def check_terms(actor, level: int) -> list[dict]:
    """What a smith adds to the die, itemised — crafting's formula with the mental stat
    the skill actually uses: **d20 + track level + half character level + Intelligence**.

    Int, because Craft is an Intelligence skill in 1e and smithing is Craft (weapons) or
    Craft (armour). Herbalism's authored Wisdom is *not* the precedent here: that number
    came from the Herbalist document's own text, which is an authored source for that
    track and says nothing about any other. Where a track has no author telling us
    otherwise, the skill's own ability governs.

    Itemised rather than summed for the reason every roll in this app is: "+9" says
    nothing, "Blacksmith 3, half level +4, Int +2" says which of the three to improve.
    """
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor else 1
    intel = int(actor.ability_mod("int")) if actor is not None else 0
    return [
        {"label": f"Blacksmith {track_level}", "value": track_level},
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intel},
    ]


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


def _chance(dc: int, bonus: int, problems=()) -> int:
    """Percent chance the check makes the DC, for the label on the button.

    Same clamp as crafting's, for the same reason: a natural 1 always fails and a
    natural 20 always succeeds, so no craft is ever certain either way and the number
    should not claim otherwise.
    """
    if problems:
        return 0
    need = dc - bonus
    return max(5, min(95, int(round(100 * (21 - need) / 20))))


def preview(level: int, chain: Chain, stock: dict | None = None,
            actor=None) -> Result:
    """What this chain would forge, and everything wrong with attempting it.

    Never raises for a chain that is merely bad — an unknown method, metal above the
    smith's tier, a cold forge all come back as `problems` so the page can grey the
    button and say why, exactly as `crafting.preview` does. `CraftError` is reserved for
    chains that cannot be described at all.

    `stock` is what the smith is carrying, as {material id: count}. Passing None means
    "assume they have it" — what every caller wants until acquisition (mining, buying)
    exists, and what the tests of the chain rules want forever.

    `actor` is the character attempting it. Supplied, the result carries the itemised
    bonus and the percentage chance; omitted, those stay at zero and the result is a
    statement about the chain rather than about anybody's odds — which is what the rules
    tests ask for and what a shelf preview shows before a character is chosen.
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
    terms = check_terms(actor, level) if actor is not None else []
    bonus = sum(t["value"] for t in terms)
    return Result(
        name=name, tier=tier, rank=rank, quality=quality, stages=chain.stages,
        dc=dc, risky=risky, weight_lb=weight, base=base,
        effects=effects, specs=specs, removed=removed, problems=problems,
        consumes=dict(wanted),
        output=_output(name, tier, rank, quality, base, effects, specs,
                       list(wanted), weight),
        bonus=bonus, terms=terms,
        chance=_chance(dc, bonus, problems) if actor is not None else 0,
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
