"""Blacksmithing: the forge's rules, in two halves.

**The step bench** (the second half of this file, docs/blacksmithing-revamp-plan.md §4,
§7, §10, §11 and docs/blacksmithing-contracts.md §7). Herbalism's revamp, mirrored: one
method at a time, each its own d20 Craft roll, then an always-played minigame whose 0..1
score the server turns into a quality tier under the smith's ceiling. Every step puts a
real thing on the shelf: ore smelts to an ingot, ingots alloy to a named bar, a bar is
forged into a blank or plate, the blank is quenched, tempered, folded and honed, and
Assemble joins head, haft and fittings (or body, fastenings and lining) into the crafted
record of contracts §4, whose numbers lane B's `forge_items.build` computes on read.

**The chain library** (the first half). The old one-shot chain (`Chain`, `preview`) that
the `/craft/` tab still drives until wave 2 retires it (contracts §1, U7). Kept working
against the new three-level track; draw, polish, rivet and flux-as-a-method are gone from
it, as from the track (plan §4.1).

The naming mirrors `crafting.py` deliberately — `TRACK_ID`, `CraftError`, `Chain`,
`preview`, `plan_step`, `make`, `failure_losses` — so a dispatch layer can route a craft
to whichever module owns the track without either module knowing about the other.

One rule is stated here because the source documents state percentages without one:

  Costs and penalties round **down**, benefits round **up**. A character is never
  surprised in the direction that hurts them — a mithral longsword at half of 4 lb is
  2 lb, and half of 5 lb is 2 lb too, because weight is a cost.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from . import effectspec
from . import worldclass as wc
from pathfindergm import files

TRACK_ID = "blacksmith"

# Methods that burn fuel. A chain that lights no fire needs none: riveting a grip onto a
# finished blade is cold work.
FUEL_BURNING = ("smelt", "forge")

# Smelting past this rank needs a fuel of at least `HOT_FUEL_RANK`: adamantine does not
# melt over charcoal. Rank 3 is "rare", so the skymetals (exotic and up) are the ones
# gated — which is the whole point of dragonfire coal existing as an entry.
HOT_METAL_RANK = 4
HOT_FUEL_RANK = 3

# Flux is no longer a method (plan §2, "Flux becomes an ingredient of Smelt"): a flux in
# a charge that is smelted cleans the *metal*, not the smith. The harm it strips is the
# harm carried by ore-kind materials, and a metal that sickens whoever works it (abysium)
# stays risky however much flux goes in the melt.
CLEANSED_BY = "smelt"

# The method that has to come last if it is used at all: a treatment goes on the
# finished piece. (Polish was this until 2026-10-03, when it merged into Hone.)
FINISHING = ("finish",)

# Each method's prerequisite, which must appear *earlier in the same chain*. This is the
# physical grammar of the forge — you cannot quench what was never forged — and it is
# what makes a chain an ordered list rather than a bag of verbs. Draw and polish left
# with the 2026-10-03 ruling, and their rows with them.
AFTER = {
    "quench": "forge",
    "temper": "quench",   # tempering is letting quenched steel back down
    "fold": "forge",
    "hone": "forge",
    "alloy": "smelt",     # alloying happens in the melt, so something must be molten
}

# Sentences for the refusals above, written once so the bench and the tests cannot
# disagree about the wording. {m} is the method, {need} its prerequisite.
_AFTER_WHY = {
    "quench": "You cannot quench what was never forged — quench follows forge.",
    "temper": "Tempering lets quenched steel back down — temper follows quench.",
    "fold": "Folding doubles hot metal over itself — fold follows forge.",
    "hone": "Honing grinds a forged edge — hone follows forge.",
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
# metal one band rarer (mixing can beat purity, OSRS Giants' Foundry). It was once the
# Blacksmith 4 route to the level-5 deed; the deed went with the 2026-10-03 ruling, so the
# step is now simply a reward, and the output is gated by the smith's level like any
# other metal (a legendary melt needs Blacksmith 3).
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
        except Exception as exc:
            files.unreadable(file, exc)
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
    # `salvage` (Harvest from a carcass) left the hub with the other three carcass
    # excursions (leatherworking lane C, plan §5.1): a carcass is harvested once, across
    # every craft, by rules/harvest.py — the smith's quench bloods are `harvest.blood.*`
    # tags on the beasts that carry them.
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
        methods=migrate_methods(_list("methods")),
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
# working edge honed. Fine is the honest step between: one of the two, not both.
#
# The shaping methods were originally required for masterwork as well, and that was
# measured to be a dead end. `rules/enchanter.py` gates every binding on a masterwork
# vessel at Enchanter *1* — "Commission one from the smith" — while fold and draw were
# Blacksmith 4, so the whole enchanting economy sat behind 140 MP of a track the
# enchanter may never have taken. Masterwork is professional work in 1e, not legendary
# work: DC 20, purchasable in any city. Under the 2026-10-03 track temper and hone are
# Blacksmith 2, so masterwork is reachable there.
MASTERWORK_DC = 20

SHAPING = ("fold",)
FINISHING_QUALITY = ("hone",)


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
    from . import tradecraft

    return [
        {"label": f"Blacksmith {track_level}", "value": track_level},
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intel},
        # Half the Craft ranks: smithing is Craft (weapons) or Craft (armour), and this
        # game keeps one Craft (option A, 2026-10-07; `tradecraft.bench_terms`).
        *tradecraft.bench_terms(actor, "blacksmith"),
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
            moved = old_method(m)
            problems.append(
                f"{track.name} has no method called {m!r}"
                + (f": {m.title()} became {moved.title()}." if moved != m else "."))
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
    if not chain.base and any(m in ("forge", "assemble") for m in chain.methods):
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
    # same-tier metals is one band rarer than either. Until 2026-10-03 the ceiling was
    # checked against the inputs only, because the stepped-up output was the one road
    # to the level-5 deed; the deed is gone, so the output is gated as well, as the
    # Herbalist's revamped bench gates a concentration by what it makes.
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
    if rank > ceiling and not any(i.rank > ceiling for i in items):
        problems.append(f"This would make {tier} metal, beyond {track.name} {level}: "
                        f"it needs {track.name} {_level_for_rank(rank) or track.max_level}.")

    quality = quality_of(chain.methods)
    dc = _dc(items, rank, chain.stages)
    if quality == "masterwork":
        # The book's own number: a masterwork component is a DC 20 piece of work in its
        # own right, so the chain is never easier than that.
        dc = max(dc, MASTERWORK_DC)

    # Effects: what every material contributes, plus what the quality adds. A flux in a
    # smelted charge strips the harm carried by dirty ore, the way purify strips a
    # poison — but only from ore: a metal that sickens the smith (abysium) is not cleaner
    # for the slag being gone.
    cleansed = CLEANSED_BY in chain.methods and any(i.kind == "flux" for i in items)
    specs: list[dict] = []
    effects: list[str] = []
    removed: list[str] = []
    from . import consumables as con

    for i in items:
        for spec in i.specs:
            marked = {**spec, "from": spec.get("from") or i.name}
            if cleansed and i.kind == "ore" and con.hurts(marked):
                removed.append(f"The flux in the melt carried off {i.name}'s impurity: "
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


def _level_for_rank(rank: int) -> int | None:
    """The first Blacksmith level whose rarity reaches this rank."""
    track = wc.get(TRACK_ID)
    for row in sorted(track.levels, key=lambda r: r.level):
        if wc.tier_rank(row.max_tier) >= rank:
            return row.level
    return None


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


# =========================================================================================
# The step bench (docs/blacksmithing-revamp-plan.md §4, §7, §10, §11; contracts §4, §7, §8)
# =========================================================================================
#
# Herbalism's step bench, for metal. The page sends a method, what is in each slot, a
# batch, the player's d20 face and the game's 0..1 score; everything else is computed here
# (or by lane B's `forge_items`, for an item's numbers). Nothing in this half reads the
# player's words: shapes come from the weapon and armour tables, materials from lane C's
# documents, the smithy from lane G's places.
#
# Three sibling lanes are built in parallel with this one and may not be merged yet:
# `rules/materials.py` (C), `rules/forge_items.py` (B), `rules/knowledge.py` (E), and
# `places.smithy_here` / `places.has_field_kit` / `market.forge_rent` (G). Each is imported
# lazily through `_lane` and every call has a stated fallback, so the bench works (more
# plainly) before they land and picks them up the moment they do, with no edit here.

import copy as _copy

METHODS = ("smelt", "alloy", "forge", "quench", "temper", "fold", "hone", "assemble",
           "finish", "strengthen", "assay")

# Station icons for the old /craft/ tab's method strip (`benches.method_glyphs` prefers a
# module's own map). Distinct within the track: the test that pins it measured eleven
# stations drawn as the same fallback crate.
METHOD_GLYPH: dict[str, str] = {
    "smelt": "🔥", "alloy": "⚗️", "forge": "🔨", "quench": "💧", "temper": "🌡️",
    "fold": "📐", "hone": "🪒", "assemble": "🔩", "finish": "✨", "strengthen": "⛓️",
    "assay": "🔍",
}

# Piece slots per gear (contracts §3, plan §6.1). The first is the main piece, counted in
# full; the others count half. The first two are required at Assemble and the third is
# optional ("a piece may be none where the base item has no such part", plan §6.1): a
# sword needs a grip, it does not need a guard.
PIECES = {"weapon": ("head", "haft", "fittings"),
          "armour": ("body", "fastenings", "lining"),
          "shield": ("body", "fastenings", "lining")}
REQUIRED_PIECES = 2

RECORD_SCHEMA = 3
BAR_FORMS = ("ingot", "bar")
PIECE_FORMS = ("blank", "plate")
WORKED_FORMS = BAR_FORMS + PIECE_FORMS + ("item",)
# Stock written by the forge. "smithing" is what `_op_prospect` writes today (plan §12.7,
# lane B fixes it); both are read so prospected ore reaches the rack either way.
BENCH_CRAFTS = (TRACK_ID, "smithing")

# Armour and shields a smith makes: the metal suits and shields of CRB Table 6-6. Leather,
# hide and padded are the tanner's; the wooden shields are a carpenter's. Three more are
# the hand-off with the leather bench (leatherworking plan §4.2, §4.5; owner Q1.3 and the
# 2026-10-08 answer 1): studded leather and the armored coat are finished from a
# leatherworker's base and from nothing else (`FROM_BASE`, the rule rows' `from_base`), and
# steel lamellar is the forge's own steel plates laced with the leatherworker's lacing set
# (the rule rows' `laced`).
FORGED_ARMOUR = ("chain shirt", "scale mail", "breastplate", "chainmail", "splint mail",
                 "banded mail", "half-plate", "full plate", "studded leather",
                 "armored coat", "steel lamellar")
FORGED_SHIELDS = ("buckler", "light shield", "heavy shield")
# Weapon families a forge shapes: the melee sections of the weapons table. Bows, firearms,
# siege engines and ammunition are other trades.
WEAPON_FAMILIES = ("Light Weapons", "One-Handed Weapons", "Two-Handed Weapons")

OLD_WORK = ("made at the old forge: it can be worn, wielded or sold, not worked further")

GROUPS = {"ore": "Ore", "ingot": "Ingots", "bar": "Bars", "blank": "Blanks and plates",
          "plate": "Blanks and plates", "fitting": "Hafts, grips and fittings",
          "fuel": "Fuel", "flux": "Flux", "quenchant": "Quenchants",
          "treatment": "Treatments", "item": "Finished work", "old": "Old work"}
# The leather forms' rack groups, kept out of GROUPS: GROUPS' keys are the forge's own form
# vocabulary, which the sound bank voices one `forge.drop.<form>` each
# (tests/test_forge_sound.py). A lacing set or a base dropped on the anvil is silent until
# the sound lane gives them a voice ("unknown events are silent", contracts §11).
LEATHER_GROUPS = {"grip": "Hafts, grips and fittings", "lacing": "Hafts, grips and fittings",
                  "base": "Leather bases"}

# Leather stock the forge's rack takes (leatherworking plan §4.4-4.5): only a form that
# fills a piece, and the piece it fills. A grip is wrapped over a weapon's haft, a lacing
# set fastens a suit; a leather base is the body of a suit the forge finishes. Measured
# before (lane D, 2026-10-08, live): the rack read every carried material whose document
# listed a piece, so once the hides listed theirs a RAW deer hide went on the rack and
# "FITS a breastplate's lining and fastenings" untanned. Raw hides, tannins, oils, waxes,
# threads and dyes are the leather bench's alone (`LEATHER_ONLY_KINDS`).
LEATHER_FILLS = {"grip": {("weapon", "haft")},
                 "lacing": {("armour", "fastenings"), ("shield", "fastenings")}}
LEATHER_ONLY_KINDS = ("hide", "tannin", "oil", "wax", "thread", "dye")


def _lane(name: str):
    """A sibling lane's module, or None while it is not merged (contracts §1). Imported on
    each call rather than at module load, so a test can stand a fake in `sys.modules`."""
    try:
        return importlib.import_module(f"rules.{name}")
    except ImportError:
        return None


def bench_rules() -> dict:
    """The track JSON's `bench` block: every number the plan marks proposed."""
    return dict(wc.get(TRACK_ID).data.get("bench") or {})


def method_row(method: str) -> dict | None:
    return (bench_rules().get("methods") or {}).get(str(method or "").strip().lower())


def from_base(shape: str) -> dict | None:
    """The rule row for a suit the forge finishes only from a leatherworker's base
    (`bench.from_base`): `{"slot": the slot the forge fills, "takes": "studs" | "plate"}`,
    or None for every other shape."""
    row = (bench_rules().get("from_base") or {}).get(str(shape or "").strip().lower())
    return dict(row) if isinstance(row, dict) else None


def laced(shape: str) -> bool:
    """Whether this forge suit's fastenings must be a leatherworker's lacing set (steel
    lamellar: the owner's answer 1 of 2026-10-08)."""
    return str(shape or "").strip().lower() in (bench_rules().get("laced") or ())


def stud_ids() -> tuple[str, ...]:
    """The studs that make studded leather: the leather bench's `forge_fittings`, the one
    list both benches read (the leather bench refuses them as "studs make a forge suit";
    the forge takes exactly these). Never a second copy here: two lists of what a stud is
    are two answers that drift."""
    lw = _lane("leatherworker")
    try:
        got = (lw.bench_rules().get("forge_fittings") or ()) if lw is not None else ()
    except Exception:          # noqa: BLE001 - no leather rules, no studs
        got = ()
    return tuple(str(x) for x in got)


def method_level(method: str) -> int:
    track = wc.get(TRACK_ID)
    for row in sorted(track.levels, key=lambda r: r.level):
        if method in row.methods:
            return row.level
    return track.max_level + 1


def old_method(name: str) -> str:
    """What a removed method became (plan §14: draw -> forge, polish -> hone, flux -> a
    Smelt ingredient, rivet -> assemble), for an old recipe or chain naming it."""
    key = str(name or "").strip().lower()
    return str((wc.get(TRACK_ID).data.get("old_methods") or {}).get(key, key))


def migrate_methods(methods) -> list[str]:
    """An old recipe's method list with the removed methods mapped onto the new (plan §14).

    Before this (measured 2026-10-04, lane H) a saved recipe naming draw or polish was
    loaded as written and refused by `preview` — "Blacksmith has no method called 'draw':
    Draw became Forge." — a sentence telling the player what the code already knew. Now
    the step is the new one: draw -> forge, polish -> hone, rivet -> assemble, and flux,
    which became an ingredient of Smelt, is the Smelt step (the flux stays in the charge,
    where Smelt reads it). A step the map produces twice in a row is one step: "forge,
    draw" was always one shaping, and is now "forge"."""
    out: list[str] = []
    for m in methods or ():
        new = old_method(str(m))
        if new and (not out or out[-1] != new) and not (new == "smelt" and "smelt" in out):
            out.append(new)
    return out


# The record an old "Iron Work" is re-derived into (plan §14). Its haft and fittings the
# old bench never recorded: they default to plain ash and iron, "value 0" — named so the
# card can say what it is made of, marked `plain` so `forge_items.build` counts nothing
# for them. A suit's fastenings are plain iron; it never had a lining.
MIGRATED_PLAIN = {"weapon": {"haft": "ash-haft", "fittings": "iron"},
                  "armour": {"fastenings": "iron"}}
MIGRATION_STAMP = "plan-14"
_OLD_QUALITY_INDEX = {"plain": 1, "fine": 2, "masterwork": 3}


def is_old_record(d) -> bool:
    """An old forge record: made by the one-shot chain, a weapon or a suit with flat
    `specs` and no `pieces` (contracts §4 has pieces; the step bench writes `forge.*`
    tags). The thing plan §14 converts on load."""
    if not isinstance(d, dict) or isinstance(d.get("pieces"), dict):
        return False
    if str(d.get("craft") or "") not in BENCH_CRAFTS:
        return False
    if any(str(p).startswith("forge.") for p in d.get("properties") or ()):
        return False
    return bool(d.get("weapon") or d.get("armour"))


def _main_material_of(d: dict) -> str:
    """The metal an old record was made of, inferred: its own `from_materials` first (the
    charge it was smelted from: a metal or alloy before an ore, an ore read as its metal),
    then the `from` its specs carry, then the longest metal name inside its own name
    ("Masterwork Cold Iron Longsword" is cold iron, not iron), and iron when nothing
    says. Only a material that can fill the main piece is an answer."""
    gear = "weapon" if d.get("weapon") else "armour"
    main = "head" if gear == "weapon" else "body"
    mats = _lane("materials")
    shelf = mats.all() if mats is not None else {}

    def fills(mid: str) -> str:
        mid = str(mid or "").strip().lower()
        doc = shelf.get(mid)
        if doc is None:
            return ""
        if doc.get("kind") == "ore" and doc.get("material") and doc["material"] != mid:
            return fills(doc["material"])
        if main in (doc.get("pieces") or {}).get(gear, ()):
            return mid
        return ""

    tried = list(d.get("from_materials") or ())
    tried.sort(key=lambda m: 0 if (shelf.get(str(m).lower()) or {}).get("kind")
               in ("metal", "alloy") else 1)
    for mid in tried:
        got = fills(mid)
        if got:
            return got
    by_name = {str(doc.get("name") or "").lower(): mid for mid, doc in shelf.items()}
    for spec in d.get("specs") or ():
        said = str((spec or {}).get("from") or "").strip().lower()
        got = fills(by_name.get(said, said))
        if got:
            return got
    name = " ".join(str(d.get("name") or d.get("base") or "").lower().split())
    for label in sorted(by_name, key=len, reverse=True):
        if label and f" {label} " in f" {name} ":
            got = fills(by_name[label])
            if got:
                return got
    return "iron"


def migrate_old_record(d: dict) -> dict | None:
    """An old "Iron Work" record re-derived as a contracts §4 record, or None when `d` is
    not one (plan §14, the owner's "convert").

    The id and name are kept, so `equipped`, a worn slot and the shelf key still find it.
    The main piece is the material inferred by `_main_material_of`; the haft and fittings
    (fastenings for a suit) are plain (`MIGRATED_PLAIN`). Masterwork stays masterwork:
    the old quality becomes the index (masterwork 3, the Superior that is masterwork at
    the new bench; fine 2; plain 1) and the flag is kept. The smith is level 1 with no
    perks — the old record never said, and level 1 cuts nothing from a negative.

    **The old record is kept beside the new one, for one version** (`migrated_from`), so
    a bad inference can be undone (`undo_migration`). Remove the field in the release
    after the one that ships this."""
    if not is_old_record(d):
        return None
    gear = "weapon" if d.get("weapon") else "armour"
    base = str(d.get("weapon") or d.get("armour") or "")
    main = "head" if gear == "weapon" else "body"
    quality = str(d.get("quality") or ("masterwork" if d.get("masterwork") else "plain"))
    q = _OLD_QUALITY_INDEX.get(quality.lower(), 1)
    pieces = {main: {"material": _main_material_of(d), "passes": 0}}
    for slot, mid in MIGRATED_PLAIN[gear].items():
        pieces[slot] = {"material": mid, "passes": 0, "plain": True}
    name = str(d.get("name") or d.get("base") or "Iron Work")
    # A shelf entry's id carries the jar's concentration ("...-longsword#1"), which is the
    # shelf key and not the thing's name; the item's own id is the slug, as the old
    # bench's output wrote it, so `item:<id>` names the blade and not the jar.
    rid = str(d.get("id") or _slug(name)).split("#", 1)[0] or _slug(name)
    return {
        "id": rid, "name": name,
        "kind": "crafted", "craft": TRACK_ID, "count": int(d.get("count", 1) or 1),
        "gear": gear, "base": base,
        "slot": str(d.get("slot") or ("hands" if gear == "weapon" else "armor")),
        "quality": wc.quality_name(q).lower(), "quality_index": q,
        "masterwork": bool(d.get("masterwork")) or quality == "masterwork",
        "pieces": pieces, "quench": None, "finish": [], "flaws": [],
        "smith": {"level": 1, "perks": {}},
        "schema": RECORD_SCHEMA, "migrated": MIGRATION_STAMP,
        "migrated_from": _copy.deepcopy(d),
    }


def undo_migration(rec: dict) -> dict | None:
    """The old record a migrated one was made from, while it is still kept."""
    old = (rec or {}).get("migrated_from")
    return _copy.deepcopy(old) if isinstance(old, dict) else None


def _mw_index() -> int:
    return int(bench_rules().get("masterwork_index", 3))


# --- materials, through lane C ----------------------------------------------------------

_FORM_BY_KIND = {"ore": "ore", "metal": "bar", "alloy": "bar", "fuel": "fuel",
                 "flux": "flux", "quenchant": "quenchant", "fitting": "fitting",
                 "treatment": "treatment"}
_FITTING_FORMS = ("haft", "grip", "guard", "fitting", "binding", "core", "lining",
                  "fastening", "fastenings", "wrap")


@dataclass
class Metal:
    """One material as the forge sees it: lane C's normalised document (contracts §3) with
    the few things the bench asks of it lifted out. `doc` is the document itself, passed
    on to lane E's knowledge functions untouched."""
    id: str
    name: str
    kind: str = "metal"
    tier: str = "common"
    form: str = ""
    parent: str = ""
    pieces: dict = field(default_factory=dict)
    working: list = field(default_factory=list)
    craft_dc: int | None = None
    doc: dict = field(default_factory=dict)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def dc(self) -> int:
        """The material's own DC: an authored craft_dc wins, else 5 + 5 x rank (the rule
        every bench in the app uses for an intermediate step)."""
        return int(self.craft_dc) if self.craft_dc is not None else 5 + 5 * self.rank

    def has(self, trait: str) -> bool:
        return trait in self.working

    def fills(self, gear: str, piece: str) -> bool:
        key = "armour" if gear in ("armour", "shield") else "weapon"
        return piece in (self.pieces.get(key) or [])

    @property
    def rack_form(self) -> str:
        f = str(self.form or "").strip().lower()
        if f in ("bar", "alloy bar", "ingot"):
            return "bar"
        if f == "ore":
            return "ore"
        if f in _FITTING_FORMS:
            return "fitting"
        if f in ("fuel", "flux", "quenchant", "treatment"):
            return f
        return _FORM_BY_KIND.get(self.kind, "fitting" if any(self.pieces.values()) else "")


def _fallback_pieces(m: Material) -> dict:
    """Which pieces an old-format material fills, until lane C's documents say (contracts
    §3 `pieces`). Read off the kind, and for fittings off the id's own word, because the
    pre-revamp file has no other record of whether a fitting is a haft or a guard. Lane
    C's `pieces` replaces this the moment it is merged."""
    if m.kind in ("metal", "alloy", "ore"):
        return {"weapon": ["head", "fittings"], "armour": ["body", "fastenings"]}
    if m.kind == "fitting":
        if "guard" in m.id:
            return {"weapon": ["fittings"]}
        if "grip" in m.id or "binding" in m.id:
            return {"weapon": ["haft"], "armour": ["lining"]}
        return {"weapon": ["haft"]}
    return {}


def _fallback_parent(mid: str) -> str:
    if mid.endswith("-ore") and mid[:-4] in materials():
        return mid[:-4]
    return mid


def metal(material_id: str) -> Metal | None:
    """The material by id, from lane C's one door (`materials.get`) when it exists, else
    from this module's own loader with the new fields at their defaults."""
    mid = str(material_id or "").strip().lower()
    if not mid:
        return None
    mats = _lane("materials")
    doc = None
    if mats is not None and hasattr(mats, "get"):
        try:
            doc = mats.get(mid)
        except Exception:          # noqa: BLE001 - a bad document is "no such material"
            doc = None
    old = materials().get(mid)
    if doc is None and old is None:
        return None
    if doc is None:
        doc = {"id": old.id, "name": old.name, "kind": old.kind, "tier": old.tier,
               "form": _FORM_BY_KIND.get(old.kind, ""), "pieces": _fallback_pieces(old),
               "weapon": [], "armour": [], "working": [], "quench_mark": None,
               "price_gp": old.price_gp, "text": old.text, "craft_dc": old.craft_dc}
    parent = ""
    if mats is not None and hasattr(mats, "material_of"):
        try:
            parent = str(mats.material_of(mid) or "")
        except Exception:          # noqa: BLE001
            parent = ""
    if not parent or parent == mid:
        parent = str(doc.get("material") or "") or _fallback_parent(mid)
    working = []
    for w in doc.get("working") or []:
        trait = w.get("trait") if isinstance(w, dict) else w
        if trait:
            working.append(str(trait))
    craft_dc = doc.get("craft_dc")
    if craft_dc is None and old is not None:
        craft_dc = old.craft_dc
    return Metal(id=mid, name=str(doc.get("name") or (old.name if old else mid)),
                 kind=str(doc.get("kind") or (old.kind if old else "metal")),
                 tier=str(doc.get("tier") or (old.tier if old else "common")),
                 form=str(doc.get("form") or ""), parent=parent,
                 pieces={k: list(v or []) for k, v in (doc.get("pieces") or {}).items()},
                 working=working, craft_dc=craft_dc, doc=dict(doc))


def _by_name(name: str) -> str:
    """A material id from a display name: prospected ore arrives as `Stock(base="Iron
    Ore")` and carries no id (rules/engine.py `_op_prospect`)."""
    want = str(name or "").strip().lower()
    for mid, m in materials().items():
        if m.name.lower() == want:
            return mid
    return ""


def _forge_relevant(m: Metal) -> bool:
    return m.kind in KIND_GLYPH or any(m.pieces.values())


def _known_keys(actor, mid: str) -> set:
    entry = (getattr(actor, "herb_known", None) or {}).get(mid) or {}
    return set(entry.get("keys") or [])


def unknown_count(actor, m: Metal | None) -> int:
    """Properties of this material the actor does not know (the rack's "?"). One store:
    `Actor.herb_known`, keyed by material id (contracts §6)."""
    kn = _lane("knowledge")
    if kn is None or actor is None or m is None:
        return 0
    try:
        keys = list(kn.property_keys(m.doc))
    except Exception:              # noqa: BLE001
        return 0
    known = _known_keys(actor, m.id)
    return sum(1 for k in keys if k not in known)


# --- what the forge puts on the shelf ---------------------------------------------------
#
# Every forge product is a `crafting.Stock` with `craft="blacksmith"`, because that is the
# one shelf the sheet saves and the engine reads. Stock has no field for a piece's passes,
# quench or build, and `crafting.Stock` belongs to no lane in this wave, so the forge's
# state travels in `Stock.properties` as hierarchical tags (`forge.form.blank`,
# `forge.passes.1`, `forge.piece.head.iron.1`): law 1's vocabulary, asked by prefix,
# and it survives a save and load untouched because `properties` already does. The record
# of contracts §4 is rebuilt from the tags (`record`), so it stores ids and passes and
# never a computed number.

# What a leather piece carries besides its material and passes (leatherworking contracts
# §4.2, the leather bench's `_piece_spec`): its form, its grade, its tannin, and a generic
# hide's beast, which `forge_items.build` reads through the harvest for the hide's inherited
# DR and resistance. Kept through the forge's tags, or a generic wolf-hide base studded at
# the forge would come out without the wolf.
PIECE_EXTRAS = ("form", "grade", "tannage", "creature")
BASE_KEYS = ("id", "name", "craft", "quality", "level")
_INT_EXTRAS = ("grade", "quality", "level")


def _enc(text: str) -> str:
    return str(text).replace(" ", "_")


def _dec(text: str) -> str:
    return str(text).replace("_", " ")


@dataclass
class Work:
    """A forge product: an ingot, a bar, a blank, a plate, or a finished item."""
    form: str
    material: str
    passes: int = 0
    quality: int | None = None
    shape: str = ""
    gear: str = ""
    quench: str = ""
    worked: list = field(default_factory=list)
    traits: list = field(default_factory=list)      # slaggy, brittle, hot_short, folded
    alloy_of: list = field(default_factory=list)    # a novel alloy's other metals
    cut: int = 0                                    # tenths cut off one bar by assaying
    pieces: dict = field(default_factory=dict)      # item: slot -> {material, passes}
    finish: list = field(default_factory=list)
    smith: dict = field(default_factory=dict)
    rid: str = ""
    name: str = ""
    tier: str = "common"
    # A suit finished from a leatherworker's base (plan §4.3): the base's id, name, craft,
    # quality index and maker's level, for provenance. Never read for a number.
    from_base: dict = field(default_factory=dict)

    def copy(self) -> "Work":
        return _copy.deepcopy(self)

    def tags(self) -> list[str]:
        t = [f"forge.form.{self.form}", f"forge.material.{self.material}"]
        if self.passes:
            t.append(f"forge.passes.{int(self.passes)}")
        if self.quality is not None:
            t.append(f"forge.quality.{int(self.quality)}")
        if self.shape:
            t.append(f"forge.shape.{_enc(self.shape)}")
        if self.gear:
            t.append(f"forge.gear.{self.gear}")
        if self.quench:
            t.append(f"forge.quench.{self.quench}")
        t += [f"forge.worked.{w}" for w in self.worked]
        t += [f"forge.trait.{x}" for x in sorted(set(self.traits))]
        t += [f"forge.alloy.{a}" for a in self.alloy_of]
        for slot, p in self.pieces.items():
            t.append(f"forge.piece.{slot}.{p['material']}.{int(p.get('passes', 0))}"
                     + (".folded" if p.get("folded") else ""))
            t += [f"forge.piecealloy.{slot}.{a}" for a in p.get("alloy_of") or []]
            for k in PIECE_EXTRAS:
                if p.get(k) not in (None, ""):
                    t.append(f"forge.pieceinfo.{slot}.{k}.{_enc(p[k])}")
        for k in BASE_KEYS:
            if self.from_base.get(k) not in (None, ""):
                t.append(f"forge.base.{k}.{_enc(self.from_base[k])}")
        t += [f"forge.finish.{f}" for f in self.finish]
        if self.smith:
            t.append(f"forge.smith.level.{int(self.smith.get('level', 1))}")
            for k, n in sorted((self.smith.get("perks") or {}).items()):
                t.append(f"forge.smith.perk.{k}.{int(n)}")
        if self.rid:
            t.append(f"forge.id.{self.rid}")
        if self.form == "item":
            t.append(f"forge.schema.{RECORD_SCHEMA}")
        if self.cut:
            t.append(f"forge.cut.{int(self.cut)}")
        return t

    @classmethod
    def from_tags(cls, tags, *, name: str = "", tier: str = "common") -> "Work | None":
        tags = [str(t) for t in (tags or []) if str(t).startswith("forge.")]
        if not any(t.startswith("forge.form.") for t in tags):
            return None
        w = cls(form="", material="", name=name, tier=tier)
        for t in tags:
            parts = t.split(".")
            head, rest = parts[1], parts[2:]
            val = ".".join(rest)
            if head == "form":
                w.form = val
            elif head == "material":
                w.material = val
            elif head == "passes":
                w.passes = int(val or 0)
            elif head == "quality":
                w.quality = int(val)
            elif head == "shape":
                w.shape = _dec(val)
            elif head == "gear":
                w.gear = val
            elif head == "quench":
                w.quench = val
            elif head == "worked":
                w.worked.append(val)
            elif head == "trait":
                w.traits.append(val)
            elif head == "alloy":
                w.alloy_of.append(val)
            elif head == "piece" and len(rest) >= 3:
                folded = rest[-1] == "folded"
                body = rest[:-1] if folded else rest
                slot, passes, mat = body[0], body[-1], ".".join(body[1:-1])
                piece = {"material": mat, "passes": int(passes or 0)}
                if folded:
                    piece["folded"] = True
                w.pieces[slot] = {**w.pieces.get(slot, {}), **piece}
            elif head == "piecealloy" and len(rest) >= 2:
                w.pieces.setdefault(rest[0], {}).setdefault("alloy_of", []).append(
                    ".".join(rest[1:]))
            elif head == "pieceinfo" and len(rest) >= 3 and rest[1] in PIECE_EXTRAS:
                v = _dec(".".join(rest[2:]))
                w.pieces.setdefault(rest[0], {})[rest[1]] = (
                    int(v) if rest[1] in _INT_EXTRAS and v.lstrip("-").isdigit() else v)
            elif head == "base" and len(rest) >= 2 and rest[0] in BASE_KEYS:
                v = _dec(".".join(rest[1:]))
                w.from_base[rest[0]] = (int(v) if rest[0] in _INT_EXTRAS
                                        and v.lstrip("-").isdigit() else v)
            elif head == "finish":
                w.finish.append(val)
            elif head == "smith" and rest:
                if rest[0] == "level":
                    w.smith["level"] = int(rest[1])
                elif rest[0] == "perk" and len(rest) >= 3:
                    w.smith.setdefault("perks", {})[rest[1]] = int(rest[2])
            elif head == "id":
                w.rid = val
            elif head == "cut":
                w.cut = int(val or 0)
        return w

    @classmethod
    def from_stock(cls, item) -> "Work | None":
        if str(getattr(item, "craft", "") or "") not in BENCH_CRAFTS:
            return None
        return cls.from_tags(getattr(item, "properties", None),
                             name=str(getattr(item, "base", "") or ""),
                             tier=str(getattr(item, "tier", "") or "common"))

    def digest(self) -> str:
        """What makes two products the same thing to stack: everything but a sliver cut."""
        sig = json.dumps([t for t in self.tags() if not t.startswith("forge.cut.")])
        return hashlib.md5(sig.encode()).hexdigest()[:10]

    @property
    def flaws(self) -> list[str]:
        return [t for t in ("brittle", "hot_short", "slaggy") if t in self.traits]


def shapes() -> dict:
    """What a smith can shape, from the engine's own tables and never from free text
    (plan §7: "the shape is picked from the engine's list of weapon and armour
    families"). Grouped by family, each with the bars it takes and the book's DC.

    Memoised on the identity of the two tables it reads, so a homebrew weapon saved at
    the weapon bench (which drops `weapons._ALL`) or a reloaded track is seen at once,
    while the dozens of names a rack asks for in one request do not rebuild 456 rows."""
    global _SHAPES
    from . import weapons as weapons_mod

    table = weapons_mod.all_weapons()
    track = wc.get(TRACK_ID)
    # Compared by identity on the objects themselves, held in the cache, so a freed table
    # can never hand its id to a new one and pass for it.
    if _SHAPES is not None and _SHAPES[0] is table and _SHAPES[1] is track:
        return _SHAPES[2]
    rules = bench_rules()
    dcs = rules.get("book_dc") or {}
    per = rules.get("bars_per_lb") or {}
    from .tables import ARMOUR, SHIELDS

    fams: dict[str, list] = {f: [] for f in WEAPON_FAMILIES}
    for key, row in sorted(table.items()):
        section = str(row.get("section") or "")
        if section not in fams or "shield" in key or row.get("category") == "ranged":
            continue
        lb = float(row.get("weight_lb") or 0)
        types = set(row.get("types") or [row.get("type")])
        fams[section].append({
            "id": key, "name": str(row.get("name") or key), "gear": "weapon",
            "prof": str(row.get("prof") or "martial"),
            "edged": bool(types & {"slashing", "piercing"}),
            "bars": max(1, math.ceil(lb / float(per.get("weapon", 4)))) if lb else 1,
            "dc": int(dcs.get(str(row.get("prof") or "martial"), dcs.get("martial", 15))),
            "pieces": list(PIECES["weapon"])})
    out = [{"family": f, "gear": "weapon", "shapes": fams[f]} for f in WEAPON_FAMILIES]
    for weight in ("light", "medium", "heavy"):
        rows = []
        for key in FORGED_ARMOUR:
            a = ARMOUR.get(key)
            if a and a.get("weight") == weight:
                rows.append({"id": key, "name": str(a.get("name") or key), "gear": "armour",
                             "edged": False,
                             "bars": max(1, math.ceil(float(a.get("lb") or 0)
                                                      / float(per.get("armour", 10)))),
                             "dc": int(dcs.get("armour_base", 10)) + int(a.get("ac", 0)),
                             "pieces": list(PIECES["armour"])})
        out.append({"family": f"{weight.title()} armour", "gear": "armour", "shapes": rows})
    rows = []
    for key in FORGED_SHIELDS:
        s = SHIELDS.get(key)
        if s:
            rows.append({"id": key, "name": str(s.get("name") or key), "gear": "shield",
                         "edged": False,
                         "bars": max(1, math.ceil(float(s.get("lb") or 0)
                                                  / float(per.get("shield", 5)))),
                         "dc": int(dcs.get("armour_base", 10)) + int(s.get("ac", 0)),
                         "pieces": list(PIECES["shield"])})
    out.append({"family": "Shields", "gear": "shield", "shapes": rows})
    got = {"families": out}
    _SHAPES = (table, track, got)
    return got


# Filled on first use and dropped by tests/conftest.py with the other content caches.
_SHAPES: tuple | None = None


def shape_info(shape: str) -> dict | None:
    """One shape by id, exactly as `shapes` lists it, or None. Weapons accept any
    spelling the weapons table knows ("Longsword", "longsword")."""
    want = str(shape or "").strip().lower()
    if not want:
        return None
    from . import weapons as weapons_mod

    wkey = weapons_mod.key_for(want) or want
    for fam in shapes()["families"]:
        for row in fam["shapes"]:
            if row["id"] == want or row["id"] == wkey:
                return row
    return None


def _shape_name(shape: str) -> str:
    info = shape_info(shape)
    return (info or {}).get("name") or str(shape or "")


def _metal_name(w: Work) -> str:
    names = []
    for mid in [w.material] + list(w.alloy_of):
        m = metal(mid)
        names.append(m.name if m else mid.replace("-", " ").title())
    return f"{'-'.join(names)} Alloy" if w.alloy_of else names[0]


def work_name(w: Work) -> str:
    """"Iron Ingot", "Steel Bar (strengthened ×2)", "Tempered Iron Blank (Longsword)",
    "Fine Iron Longsword" (contracts §4's example). The rack shows quality on its own
    badge, so only a finished item carries it in its name."""
    metal_name = _metal_name(w)
    if w.form == "item" and w.from_base:
        # Named as the leather bench names its suits ("Fine Deer Studded Leather"), the
        # hide's word without "Hide": the body is the tanner's, the studs are the smith's.
        lw = _lane("leatherworker")
        lead = getattr(lw, "_lead_word", None) if lw is not None else None
        if lead is not None:
            try:
                metal_name = str(lead(w.material)) or metal_name
            except Exception:      # noqa: BLE001 - the material's own name will do
                pass
    if w.form == "item":
        q = int(w.quality or 0)
        prefix = "" if q == 1 else f"{wc.quality_name(q)} "
        return f"{prefix}{metal_name} {_shape_name(w.shape).title()}".strip()
    words = []
    if "temper" in w.worked:
        words.append("Tempered")
    elif w.quench:
        words.append("Quenched")
    if "hone" in w.worked:
        words.append("Honed")
    if "folded" in w.traits:
        words.append("Folded")
    noun = {"ingot": "Ingot", "bar": "Bar", "blank": "Blank", "plate": "Plate"}.get(
        w.form, w.form.title())
    name = " ".join(words + [metal_name, noun])
    if w.form in PIECE_FORMS and w.shape:
        name += f" ({_shape_name(w.shape).title()})"
    if w.passes:
        name += f" (strengthened ×{w.passes})" if w.form in BAR_FORMS \
            else f", strengthened ×{w.passes}"
    return name


def _slot_of(gear: str) -> str:
    return {"weapon": "hands", "armour": "armor", "shield": "shield"}.get(gear, "hands")


def to_stock(w: Work):
    """The forge product as a shelf entry. A finished weapon points `weapon` at its base,
    so it is wieldable as what it really is before lane B's reader of the build lands."""
    from .crafting import Stock

    item = w.form == "item"
    mats = ([p.get("material") for p in w.pieces.values()] if item
            else [w.material] + list(w.alloy_of))
    return Stock(
        base=w.name or work_name(w), tier=w.tier, count=1, craft=TRACK_ID,
        kind="crafted" if item else w.form,
        slot=_slot_of(w.gear) if item else None, wearable=item,
        how=[] if item else ["ingredient"],
        weapon=w.shape if item and w.gear == "weapon" else None,
        armour=w.shape if item and w.gear == "armour" else None,
        masterwork=bool(item and int(w.quality or 0) >= _mw_index()),
        from_materials=[m for m in mats if m],
        properties=w.tags())


def stock_key(w: Work) -> str:
    """The shelf key: the name's slug and the digest of what it is. Not `Stock.id`, which
    is the name and a concentration: two Fine Iron Longswords on different hafts have the
    same name and must not stack into one."""
    return f"{_slug(w.name or work_name(w))}~{w.digest()}"


def put(actor, w: Work, count: int = 1) -> str:
    """Put a product on the shelf, stacking with an identical one. Returns its key."""
    if not w.name:
        w.name = work_name(w)
    key = stock_key(w)
    have = actor.stock.get(key)
    if have is not None:
        have.count = int(have.count or 0) + int(count)
    else:
        st = to_stock(w)
        st.count = int(count)
        actor.stock[key] = st
    return key


def record(item, count: int | None = None) -> dict | None:
    """The crafted record of contracts §4, rebuilt from a forge item's tags, or None for
    anything else. Public so lane B's readers can ask it of any Stock."""
    w = item if isinstance(item, Work) else Work.from_stock(item)
    if w is None or w.form != "item":
        return None
    q = int(w.quality or 0)
    n = int(count if count is not None else getattr(item, "count", 1) or 1)
    rec = {
        "id": w.rid or _slug(w.name), "name": w.name or work_name(w),
        "kind": "crafted", "craft": TRACK_ID, "count": n,
        "gear": w.gear, "base": w.shape, "slot": _slot_of(w.gear),
        "quality": wc.quality_name(q).lower(), "quality_index": q,
        "masterwork": q >= _mw_index(),
        "pieces": _copy.deepcopy(w.pieces),
        "quench": w.quench or None, "finish": list(w.finish), "flaws": w.flaws,
        "smith": _copy.deepcopy(w.smith) or {"level": 1, "perks": {}},
        "schema": RECORD_SCHEMA,
    }
    if w.from_base:
        rec["from_base"] = dict(w.from_base)
    return rec


def records(actor) -> list[dict]:
    """Every finished forge item the actor carries, as records (contracts §4)."""
    out = []
    for item in (getattr(actor, "stock", {}) or {}).values():
        rec = record(item)
        if rec is not None:
            out.append(rec)
    return out


def build_of(rec: dict | None) -> dict | None:
    """Lane B's `forge_items.build(record)`, or None while it is not merged: the page then
    shows the pieces without a sum rather than numbers this lane made up."""
    fi = _lane("forge_items")
    if rec is None or fi is None or not hasattr(fi, "build"):
        return None
    return fi.build(rec)


def preview_of(pieces: dict, *, gear: str, base: str, quality_index: int, level: int,
               perks: dict) -> dict | None:
    """Lane B's `forge_items.preview` (contracts §4), or None while it is not merged."""
    fi = _lane("forge_items")
    if fi is None or not hasattr(fi, "preview") or not pieces:
        return None
    return fi.preview(pieces, gear=gear, base=base, quality_index=int(quality_index),
                      level=int(level), perks=dict(perks))


# --- the rack ---------------------------------------------------------------------------

@dataclass
class Piece:
    """One rack entry (UI plan §6.2): raw material from the satchel's counts, or a forge
    product from the shelf. `count` is whole units usable; `amount` adds the part of a
    bar an assay has left ("Iron bar 1.9")."""
    key: str
    name: str
    material: str
    form: str
    count: int
    tier: str = "common"
    work: Work | None = None
    cut: int = 0
    old: str = ""
    # Leather stock (plan §4.4-4.5): `leather` is the leather bench's own record of a grip
    # or a lacing set (`leatherworker.Hide`), `base` a leatherworker's finished record that
    # names suits it is the base for. `worn` is said in words by `fit_reason`.
    leather: object | None = None
    base: dict | None = None
    worn: bool = False

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def from_leather(self) -> bool:
        """Leather stock: the tanner's work, which the smith only fits."""
        return self.leather is not None or self.base is not None

    @property
    def amount(self) -> float:
        return round(self.count + ((10 - self.cut) / 10 if self.cut else 0), 1)

    @property
    def passes(self) -> int:
        return int(self.work.passes) if self.work else 0

    @property
    def quality(self) -> int | None:
        if self.base is not None:
            q = self.base.get("quality_index")
            return int(q) if q is not None else None
        if self.leather is not None:
            return getattr(self.leather, "quality", None)
        return self.work.quality if self.work else None

    @property
    def traits(self) -> list[str]:
        if self.work is not None:
            return list(self.work.traits)
        m = metal(self.material)
        return ["slaggy"] if m and m.has("slaggy") else []

    def as_work(self) -> Work:
        """This entry as a forge product, so a bought bar and a smelted ingot are worked
        the same way. A raw slaggy bar is slaggy (plan §5.5). Leather stock is never a bar:
        `fit_reason` keeps it out of every step that would ask."""
        if self.work is not None:
            return self.work.copy()
        if self.from_leather:
            raise CraftError(f"{self.name} is leather work, not metal to be worked.")
        m = metal(self.material)
        form = "ingot" if self.form == "ingot" else "bar"
        return Work(form=form, material=self.material, tier=self.tier,
                    traits=["slaggy"] if m and m.has("slaggy") else [])

    def badges(self) -> list[str]:
        w = self.work
        out = []
        if w is not None:
            if w.quench:
                out.append("quenched")
            if "temper" in w.worked:
                out.append("tempered")
            if "hone" in w.worked:
                out.append("honed")
            if w.passes:
                out.append(f"strengthened ×{w.passes}")
        if self.base is not None:
            out.append("leather base")
        if self.leather is not None:
            out.append(f"grade {int(getattr(self.leather, 'grade', 0) or 0)}")
        if self.worn:
            out.append("worn")
        for t in self.traits:
            out.append(t.replace("_", "-"))
        return out

    def as_item(self, actor=None) -> dict:
        m = metal(self.material) if self.material else None
        d = {"key": self.key, "name": self.name, "material": self.material,
             "form": self.form,
             "group": (LEATHER_GROUPS.get(self.form) if self.from_leather else None)
             or GROUPS.get(self.form, "Other"),
             "count": self.count, "amount": self.amount, "tier": self.tier,
             "rank": self.rank, "glyph": KIND_GLYPH.get(m.kind, "🪨") if m else "🪨",
             "passes": self.passes, "quality": self.quality,
             "quality_name": wc.quality_name(self.quality) if self.quality is not None
             else None,
             "badges": self.badges(),
             "unknown": unknown_count(actor, m) if m else 0,
             "old": self.old}
        if self.work is not None:
            d["shape"] = self.work.shape
            d["gear"] = self.work.gear
            if self.work.quench:
                d["quench"] = self.work.quench
            if self.work.form == "item":
                d["record"] = record(self.work, self.count)
        if self.base is not None:
            d["record"] = _copy.deepcopy(self.base)
            d["gear"] = str(self.base.get("gear") or "armour")
            d["base_for"] = list(self.base.get("base_for") or [])
        if self.from_leather:
            d["leather"] = True
            d["fills"] = sorted(slot for _g, slot in LEATHER_FILLS.get(self.form, ())) \
                or (["body"] if self.base is not None else [])
        return d


def _worn_ids(actor) -> set[str]:
    out = set()
    for rec in (getattr(actor, "worn", None) or {}).values():
        if isinstance(rec, dict) and rec.get("id"):
            out.add(str(rec["id"]).strip().lower())
    return out


def _leather_piece(actor, sid: str, st, reserved: dict) -> Piece | None:
    """A leather shelf entry as the forge sees it, or None when the forge has no use for
    it (plan §4.5): a grip or a lacing set from the leather bench (`leatherworker.Hide`,
    form `grip` or `lacing`), or a leatherworker's finished record that is a base for a
    suit the forge finishes (`base_for`, plan §4.3). Green hides, leather by the hide,
    panels, plates and finished goods that are no base stay on the leather bench."""
    key = f"stock:{sid}"
    count = int(getattr(st, "count", 0) or 0) - int(reserved.get(key, 0))
    if count <= 0:
        return None
    rec = getattr(st, "record", None)
    if isinstance(rec, dict):
        if rec.get("craft") != "leatherworker" or not rec.get("base_for"):
            return None
        body = (rec.get("pieces") or {}).get("body") or {}
        rid = str(rec.get("id") or "").strip().lower()
        return Piece(key=key, name=str(getattr(st, "name", "") or rec.get("name") or sid),
                     material=str(body.get("material") or ""), form="base", count=count,
                     tier=str(rec.get("tier") or getattr(st, "tier", "") or "common"),
                     base=_copy.deepcopy(rec), worn=bool(rid and rid in _worn_ids(actor)))
    lw = _lane("leatherworker")
    if lw is None or str(getattr(st, "craft", "") or "") != getattr(lw, "TRACK_ID", ""):
        return None
    h = lw.Hide.from_stock(st)
    if h is None or h.form not in LEATHER_FILLS:
        return None
    return Piece(key=key, name=str(getattr(st, "name", "") or h.name or sid),
                 material=h.material, form=h.form, count=count, tier=h.tier_name, leather=h)


def off_rack_reason(actor, key: str) -> str:
    """Why a carried thing the page put on the anvil is not on the forge's rack, in words,
    or "" when this rule has nothing to say (it is simply not carried). A raw or bought hide,
    a tannin and leather not yet cut into a piece are the leather bench's (`LEATHER_FILLS`):
    the refusal says so, rather than "no longer on your rack" about a hide still in the pack."""
    kind, _, ident = str(key or "").partition(":")
    if kind == "inv" and int((getattr(actor, "inventory", {}) or {}).get(ident, 0) or 0) > 0:
        m = metal(ident)
        if m is not None and m.kind in LEATHER_ONLY_KINDS:
            if m.kind == "hide":
                return (f"{m.name} is a hide, not yet a piece the forge can use: tan it and "
                        f"cut it at the leather bench into a grip, a lacing set or a base.")
            return f"{m.name} is a tanner's material: it is used at the leather bench."
    if kind == "stock":
        st = (getattr(actor, "stock", {}) or {}).get(ident)
        lw = _lane("leatherworker")
        h = lw.Hide.from_stock(st) if (st is not None and lw is not None) else None
        if h is not None and h.form not in LEATHER_FILLS:
            return (f"{st.name} is not yet a piece the forge can use: cut it at the leather "
                    f"bench into a grip, a lacing set or a base.")
        rec = getattr(st, "record", None)
        if isinstance(rec, dict) and rec.get("craft") == "leatherworker":
            return f"{st.name} is finished leather work, not a base for anything the forge makes."
    return ""


def rack(actor, reserved: dict | None = None) -> list[Piece]:
    """Everything the forge can reach for: only what is carried (UI plan §6.2). Raw
    materials from `Actor.inventory` (bought, gathered), and from the shelf the forge's
    own products plus prospected ore. `reserved` is `{key: count}` held by a step between
    its roll and its finish."""
    reserved = reserved or {}
    out: list[Piece] = []
    if actor is None:
        return out
    for iid, n in sorted((getattr(actor, "inventory", {}) or {}).items()):
        if int(n or 0) <= 0:
            continue
        m = metal(iid)
        if m is None or not _forge_relevant(m) or m.kind in LEATHER_ONLY_KINDS:
            # A hide in the satchel is raw or bought leather by the hide (it arrives in its
            # `sold_as` form): neither is a grip, a lacing set or a base until the leather
            # bench cuts it into one (`LEATHER_FILLS`).
            continue
        key = f"inv:{m.id}"
        count = int(n) - int(reserved.get(key, 0))
        if count > 0:
            out.append(Piece(key=key, name=m.name, material=m.id, form=m.rack_form,
                             count=count, tier=m.tier))
    for sid, st in sorted((getattr(actor, "stock", {}) or {}).items(),
                          key=lambda kv: kv[1].name.lower()):
        if str(st.craft or "") not in BENCH_CRAFTS:
            got = _leather_piece(actor, sid, st, reserved)
            if got is not None:
                out.append(got)
            continue
        key = f"stock:{sid}"
        whole = int(st.count or 0)
        w = Work.from_stock(st)
        if w is not None:
            # The bar an assay has cut into is the last of the stack: whole bars are
            # the rest (plan §9.2, "bars track tenths").
            avail = whole - (1 if w.cut else 0) - int(reserved.get(key, 0))
            if avail <= 0 and not w.cut:
                continue
            out.append(Piece(key=key, name=st.name, material=w.material, form=w.form,
                             count=max(0, avail), tier=w.tier, work=w, cut=w.cut))
            continue
        count = whole - int(reserved.get(key, 0))
        if count <= 0:
            continue
        m = metal(_by_name(st.base))
        if m is not None:
            out.append(Piece(key=key, name=st.name, material=m.id, form=m.rack_form,
                             count=count, tier=m.tier))
        else:
            out.append(Piece(key=key, name=st.name, material="", form="old", count=count,
                             tier=str(st.tier or "common"), old=OLD_WORK))
    return out


# --- where you smith (lane G, contracts §8) ----------------------------------------------

def where_here(scene, actor, known=()) -> dict:
    """{"smithy": lane G's smithy dict or None, "kit": carrying a field kit}.

    Asked of `places.smithy_here(scene, known)` and `places.has_field_kit(actor)`, never
    of the player's words (plan §10). `known` is `Engine.places()`, which lane G needs for
    an authored place whose id does not spell its name. Before lane G is present there is
    no smithy anywhere and the kit folds out wherever the character stands, which is how
    the forge worked before the revamp."""
    places = _lane("places")
    smithy, kit = None, True
    fn = getattr(places, "smithy_here", None) if places is not None else None
    if fn is not None:
        try:
            smithy = fn(scene, known) or None
        except Exception:          # noqa: BLE001 - a place we cannot read is no smithy
            smithy = None
    fk = getattr(places, "has_field_kit", None) if places is not None else None
    if fk is not None:
        try:
            kit = bool(fk(actor))
        except Exception:          # noqa: BLE001
            kit = False
    return {"smithy": smithy, "kit": kit}


def rent_cp(scene, smithy: dict | None, minutes: int, known=()) -> int:
    """What the forge here charges for the hours (plan §10), asked of lane G's
    `market.forge_rent`, which knows that your own smithy is free and a friend's is not.
    Never computed from a rate here while that exists: a second answer to what the smith
    charges is how two numbers drift. The smithy's own `rate_cp_per_hour` is the fallback
    only while lane G is absent."""
    if not smithy or minutes <= 0:
        return 0
    hours = minutes / 60
    market = _lane("market")
    fn = getattr(market, "forge_rent", None) if market is not None else None
    if fn is not None:
        return max(0, int(fn(scene, hours, known)))
    return max(0, int(math.ceil(round(int(smithy.get("rate_cp_per_hour") or 0) * hours,
                                      6))))


def methods_view(level: int, where: dict | None = None) -> list[dict]:
    """The method strip (UI plan §6.1): every method in craft order, with its lock in
    words: "Blacksmith 2", "Needs a smithy", "Needs a field kit or a smithy"."""
    where = where or {"smithy": None, "kit": True}
    rules = bench_rules()
    out = []
    for mid in rules.get("order") or METHODS:
        row = (rules.get("methods") or {}).get(mid) or {}
        need = method_level(mid)
        reason = ""
        if need > int(level):
            reason = f"Blacksmith {need}"
        elif row.get("where") == "smithy" and not where.get("smithy"):
            reason = "Needs a smithy"
        elif not where.get("smithy") and not where.get("kit"):
            reason = "Needs a field kit or a smithy"
        out.append({"id": mid, "name": row.get("name", mid.title()), "level": need,
                    "where": row.get("where", "kit"), "bulk": bool(row.get("bulk")),
                    "locked": bool(reason), "lock_reason": reason,
                    "takes": row.get("takes", ""), "makes": row.get("makes", ""),
                    "glyph": METHOD_GLYPH.get(mid, "")})
    return out


# --- whether one thing fits a slot --------------------------------------------------------

METHOD_SLOTS = {
    "smelt": ("ore", "fuel", "flux"),
    "forge": ("metal", "fuel"),
    "quench": ("piece", "quenchant"),
    "temper": ("piece",),
    "fold": ("piece", "with", "flux"),
    "hone": ("piece",),
    "finish": ("item", "treatment"),
    "strengthen": ("bar", "flux"),
}
OPTIONAL = {"smelt": ("flux",), "fold": ("with", "flux"), "strengthen": ("flux",)}

_MISSING = {
    "ore": "Put ore in the furnace.",
    "fuel": "Add fuel: the fire needs feeding.",
    "metal": "Put a bar or ingot on the anvil.",
    "piece": "Put a blank or plate on the anvil.",
    "quenchant": "Choose a quenchant for the bath.",
    "item": "Put a finished item on the bench.",
    "treatment": "Choose a treatment.",
    "bar": "Put bars of one metal on the anvil.",
    "head": "Put a blank in the head slot.",
    "haft": "Put a haft or grip in the haft slot.",
    "body": "Put a plate in the body slot.",
    "fastenings": "Put fastenings in the fastenings slot.",
}


def _alloy_ids() -> set[str]:
    out = set()
    for r in (bench_rules().get("alloys") or {}).values():
        for part in r.get("parts") or []:
            out |= set(part.get("any") or []) | ({part["id"]} if part.get("id") else set())
    return out


def _a(noun: str) -> str:
    return ("an " if noun[:1] in "aeiou" else "a ") + noun


def _edged(shape: str) -> bool:
    return bool((shape_info(shape) or {}).get("edged"))


def fit_reason(method: str, slot: str, p: Piece, *, gear: str = "") -> str:
    """Why this rack entry cannot go in this slot for this method, in words, or "" when
    it fits. Every dimmed row carries one (UI plan §6.2: never colour alone)."""
    if p.old:
        return p.old
    if p.count <= 0:
        return "only part of a bar is left of it"
    f, w = p.form, p.work
    m = metal(p.material)
    if method == "smelt":
        want = {"ore": ("ore",), "fuel": ("fuel",), "flux": ("flux",)}.get(slot, ())
        return "" if f in want else {"ore": "only ore goes in the furnace",
                                     "fuel": "that is not fuel",
                                     "flux": "that is not a flux"}.get(slot, "no such slot")
    if method == "alloy":
        if f in BAR_FORMS or (m is not None and m.id in _alloy_ids() and f != "item"
                              and f not in PIECE_FORMS):
            return ""
        return "only ingots, bars and what an alloy recipe names go in the crucible"
    if method == "forge":
        if slot == "metal":
            return "" if f in BAR_FORMS else "forge works bars and ingots"
        return "" if f == "fuel" else "that is not fuel"
    if method in ("quench", "temper", "hone") and slot == "piece":
        if f not in PIECE_FORMS:
            return "only a blank or a plate is worked here"
        if method == "quench" and w.quench:
            return "it has already been quenched"
        if method == "temper":
            if not w.quench:
                return "it has not been quenched: temper follows quench"
            if "temper" in w.worked:
                return "it is already tempered"
        if method == "hone":
            if w.gear != "weapon":
                return "only a weapon blank has an edge"
            if not _edged(w.shape):
                return f"a {_shape_name(w.shape).lower()} has no edge to hone"
            if "hone" in w.worked:
                return "it is already honed"
        return ""
    if method == "quench" and slot == "quenchant":
        return "" if f == "quenchant" else "that is not a quenchant"
    if method in ("fold", "strengthen") and slot == "flux":
        return "" if f == "flux" else "that is not a flux"
    if method == "fold":
        if slot == "with":
            return "" if f in BAR_FORMS else "only a second bar can be folded in"
        if f not in BAR_FORMS + PIECE_FORMS:
            return "fold works a bar, an ingot, a blank or a plate"
        if "folded" in p.traits and "slaggy" not in p.traits:
            return "it is already folded: folding clean metal again adds nothing"
        return ""
    if method == "strengthen":
        return "" if f in BAR_FORMS else "strengthen welds bars and ingots"
    if method == "assemble":
        gear = gear or ("weapon" if slot in PIECES["weapon"] else "armour")
        main = PIECES[gear][0]
        if p.worn:
            return "you are wearing it: take it off before the smith works it"
        if f == "base":
            # A leather base is the body of a suit the forge finishes (plan §4.3).
            if slot != "body" or gear != "armour":
                return "a leather base is a suit's body"
            if not [s for s in (p.base or {}).get("base_for") or () if from_base(s)]:
                return f"{p.name} is not a base for anything the forge finishes"
            return ""
        if slot == main:
            if f not in PIECE_FORMS:
                return (f"the {slot} is a forged {'blank' if gear == 'weapon' else 'plate'}"
                        + ("" if gear == "weapon" else " or a leather base"))
            want = ("weapon",) if slot == "head" else ("armour", "shield")
            if w.gear not in want:
                return f"that is not shaped for a {slot}"
            rule = from_base(w.shape)
            if rule:
                # Studded leather and the armored coat start from a leatherworker's base
                # (owner Q1.3): a metal plate shaped for one is its lining, never its body.
                shape = _shape_name(w.shape).lower()
                return (f"{_a(shape)} is finished from a leather base: put the base in the "
                        f"body" + (" and these plates in the lining"
                                   if rule.get("takes") == "plate" else ""))
            return ""
        if f in LEATHER_FILLS:
            if (gear, slot) in LEATHER_FILLS[f]:
                return ""
            return ("a grip is wrapped over a weapon's haft" if f == "grip"
                    else "a lacing set fastens a suit or a shield")
        if f == "plate" and slot == "lining" and w is not None:
            rule = from_base(w.shape)
            if rule and rule.get("slot") == "lining" and rule.get("takes") == "plate":
                return ""
        if f in PIECE_FORMS or f == "item":
            return f"a worked piece cannot be the {slot}"
        if m is None or not m.fills(gear, slot):
            return f"{p.name} does not make a {slot}"
        return ""
    if method == "finish":
        if slot == "item":
            return "" if f == "item" else "only a finished item takes a finish"
        sacred = set(bench_rules().get("sacred_finishes") or [])
        if m is not None and (m.kind == "treatment" or m.id in sacred):
            return ""
        return "that is not a treatment"
    return "no such slot"


def assemble_slots(gear: str) -> tuple[str, ...]:
    return PIECES.get(gear, PIECES["weapon"])


def fits_for(method: str, items: list[Piece], *, gear: str = "") -> dict:
    """`{slot: {key: reason or ""}}` for every rack entry and every slot of the method,
    which is what dims rows (contracts §7 `check`)."""
    names = METHOD_SLOTS.get(method)
    if method == "assemble":
        names = assemble_slots(gear or "weapon")
    elif method == "alloy":
        names = ("part",)
    return {slot: {p.key: fit_reason(method, slot, p, gear=gear) for p in items}
            for slot in names or ()}


# --- one step ---------------------------------------------------------------------------

@dataclass
class ForgePlan:
    """What one step would do: everything `check` shows, `roll` gates on and `finish`
    makes. Built fresh for every request; nothing in it is trusted from the page."""
    method: str
    batch: int = 1
    slots: dict = field(default_factory=dict)       # slot -> (Piece, count per unit)
    problems: list = field(default_factory=list)
    dc: int = 0
    bonus: int = 0
    terms: list = field(default_factory=list)
    need: int | None = None
    impossible: str = ""
    minutes: int = 0
    units: int = 0
    consumes: list = field(default_factory=list)    # (Piece, total)
    outputs: list = field(default_factory=list)     # (Work, count) before the tier
    lead: Metal | None = None
    rank_in: int = 1
    rank_out: int = 1
    tier: str = "common"
    level: int = 1
    ceiling: int = 2
    step_ceiling: int = 2
    shape: str = ""
    gear: str = ""
    masterwork_work: bool = False
    masterwork_why: str = ""
    aim: bool = True                                # aiming for masterwork at Assemble
    perks: dict = field(default_factory=dict)
    working: list = field(default_factory=list)
    fuel: Metal | None = None
    flux: Metal | None = None
    yields: bool = False
    smithy: bool = False
    name: str = ""
    noun: str = ""

    @property
    def can_roll(self) -> bool:
        return not self.problems and self.need is not None and self.units > 0

    @property
    def info(self) -> str:
        """The line under the stage (UI plan §6.3): "1 blank. 1h 30m. DC 15, you need 9 or
        better." Every number in it is this plan's."""
        if not self.units:
            return ""
        n = sum(c for _, c in self.outputs) or self.units
        hours, mins = divmod(int(self.minutes), 60)
        span = (f"{hours}h {mins}m" if hours and mins else f"{hours}h" if hours
                else f"{mins}m")
        word = self.noun + ("" if n == 1 else "s")
        line = f"{n} {word}. {span}. DC {self.dc}"
        if self.need is None:
            return f"{line}: {self.impossible}."
        return f"{line}, you need {self.need} or better."


def _perk_counts(progress) -> dict:
    held = getattr(progress, "perks", {}) or {}
    return {p: int(held.get(p, 0)) for p in ("potency", "hardening", "quality", "yield")}


def plan_step(actor, progress, method: str, slots: dict, batch: int = 1, *,
              shape: str = "", where: dict | None = None,
              masterwork: bool = True) -> ForgePlan:
    """One step, worked out without changing anything.

    `slots` maps a slot name to (rack Piece, count per unit); the count is read only by
    Alloy, whose ratio is the player's choice, and fixed by the rule everywhere else.
    `where` is `where_here`'s answer; None means a field kit and no smithy, which is what
    the rules tests want. `masterwork` is the smith's ambition at Assemble (the sweep's
    Burning Wheel lesson: choose before the roll): aiming for Superior raises the DC to
    the book's 20, and not aiming caps the work at Fine.
    """
    method = str(method or "").strip().lower()
    level = int(getattr(progress, "level", 1) or 1)
    batch = max(1, int(batch or 1))
    where = where or {"smithy": None, "kit": True}
    plan = ForgePlan(method=method, batch=batch, slots=dict(slots or {}), level=level,
                     perks=_perk_counts(progress), shape=str(shape or "").strip(),
                     aim=bool(masterwork),
                     ceiling=wc.ceiling_index(progress) if progress is not None else 2)
    plan.step_ceiling = plan.ceiling
    row = method_row(method)
    if row is None:
        plan.problems.append(f"There is no forge step called {method!r}.")
        return plan
    if method == "assay":
        plan.problems.append("An assay is not worked at the anvil: assay the material "
                             "from its card.")
        return plan
    plan.terms = check_terms(actor, level)
    plan.bonus = sum(t["value"] for t in plan.terms)
    need = method_level(method)
    if need > level:
        plan.problems.append(f"{row['name']} is learned at Blacksmith {need}.")
    plan.smithy = row.get("where") == "smithy"
    if plan.smithy and not where.get("smithy"):
        plan.problems.append(f"{row['name']} needs a smithy: a furnace and a "
                             f"forge-welding hearth, not a field kit.")
    elif not where.get("smithy") and not where.get("kit"):
        plan.problems.append("You have no field kit with you, and there is no smithy "
                             "here.")
    if batch > 1 and not row.get("bulk"):
        plan.problems.append(f"{row['name']} works one piece at a time; there is no "
                             f"batch.")
        return plan

    # Every slot the page filled must fit before anything is worked out.
    gear = ""
    if method == "assemble":
        main = plan.slots.get("head") or plan.slots.get("body")
        gear = (main[0].work.gear if main and main[0].work is not None else "") or \
            ("weapon" if "head" in plan.slots else "armour")
        plan.gear = gear
    for slot, (p, n) in plan.slots.items():
        why = fit_reason(method, "part" if method == "alloy" else slot, p, gear=gear)
        if why:
            plan.problems.append(f"{p.name}: {why}.")
        if int(n) <= 0:
            plan.problems.append(f"{p.name}: a count of {n} is nothing.")
    if plan.problems:
        return plan

    _BUILD[method](plan, row)
    if plan.problems:
        return plan

    # Enough of everything, across the whole batch, counting one piece used twice.
    used: dict[str, list] = {}
    for p, n in plan.consumes:
        used.setdefault(p.key, [p, 0])[1] += int(n)
    for p, n in used.values():
        if n > p.count:
            plan.problems.append(f"{p.name}: the step wants {n} and you carry {p.count}.")

    # Rarity: the level's band, and the smithy for rare and up (plan §4.1, §10).
    track = wc.get(TRACK_ID)
    top = wc.tier_rank(track.at(level).max_tier)
    smithy_rank = int(bench_rules().get("smithy_rank", 3))
    # Leather stock is the tanner's work, which the smith only fits: a sharkskin grip or a
    # red dragonhide base is not metal the smith's level must reach (leatherworking plan
    # §4.4-4.5). The forge's own pieces on the same anvil are gated as ever.
    seen = []
    for p, _ in plan.consumes:
        if p.material and p.material not in seen and not p.from_leather:
            seen.append(p.material)
    for w, _ in plan.outputs:
        for mid in ([] if w.from_base else [w.material]) + list(w.alloy_of):
            if mid and mid not in seen:
                seen.append(mid)
    for mid in seen:
        m = metal(mid)
        if m is None:
            continue
        if m.rank > top:
            lvl = _level_for_rank(m.rank)
            plan.problems.append(f"{m.name} is {m.tier}; Blacksmith {level} works "
                                 f"{wc.TIERS[top - 1]} at best"
                                 + (f": it needs Blacksmith {lvl}." if lvl else "."))
        elif m.rank >= smithy_rank and not where.get("smithy"):
            plan.problems.append(f"{m.name} is {m.tier}: rare and rarer metal needs a "
                                 f"smithy, not a field kit.")
    if plan.rank_out > top and not any("needs Blacksmith" in x for x in plan.problems):
        lvl = _level_for_rank(plan.rank_out)
        plan.problems.append(f"This would make {wc.TIERS[plan.rank_out - 1]} metal, "
                             f"beyond Blacksmith {level}"
                             + (f": it needs Blacksmith {lvl}." if lvl else "."))
    plan.tier = wc.TIERS[max(1, min(len(wc.TIERS), plan.rank_out)) - 1]

    from .crafting import check_odds

    plan.need, plan.impossible = check_odds(plan.dc, plan.bonus)
    plan.step_ceiling = max(0, plan.step_ceiling)
    return plan


def _piece(plan: ForgePlan, slot: str, *, optional: bool = False):
    got = plan.slots.get(slot)
    if not got:
        if not optional:
            plan.problems.append(_MISSING.get(slot, f"Fill the {slot} slot."))
        return None
    return got[0]


def _minutes(plan: ForgePlan, row: dict, units: int, key: str = "minutes") -> int:
    base = int(row.get(key, row.get("minutes", 0)) or 0) * max(1, units)
    scale = 1.0
    traits = bench_rules().get("traits") or {}
    if plan.lead is not None:
        for t in plan.lead.working:
            scale *= float((traits.get(t) or {}).get("time", 1.0))
    return int(round(base * scale))


def _slag_cap(plan: ForgePlan, w: Work | None) -> None:
    # Slaggy: the quality ceiling is one lower until the metal is folded (plan §5.5).
    if w is not None and "slaggy" in w.traits:
        plan.step_ceiling = min(plan.step_ceiling, plan.ceiling - 1)


def _build_smelt(plan: ForgePlan, row: dict) -> None:
    ore = _piece(plan, "ore")
    fuel = _piece(plan, "fuel")
    flux = _piece(plan, "flux", optional=True)
    if plan.problems:
        return
    rules = bench_rules()
    units = plan.batch
    m, fm = metal(ore.material), metal(fuel.material)
    xm = metal(flux.material) if flux else None
    parent = metal(m.parent) or m
    if m.rank >= int(rules.get("hot_metal_rank", 4)) \
            and fm.rank < int(rules.get("hot_fuel_rank", 3)):
        plan.problems.append(f"{m.name} does not melt over {fm.name.lower()}: smelting "
                             f"{m.tier} ore needs a fuel of rare tier or better.")
        return
    plan.consumes = [(ore, int(row.get("ore_per_unit", 2)) * units),
                     (fuel, int(row.get("fuel_per_unit", 2)) * units)]
    if flux is not None:
        plan.consumes.append((flux, int(row.get("flux_per_unit", 1)) * units))
    # A flux in the charge carries off the slag (plan §7: "flux cancels slaggy"). One
    # whose document names its working traits must name `cleans_slag`; one from before
    # the data pass, which names none, is taken at its kind's word.
    cleans = xm is not None and (xm.has("cleans_slag") or not xm.working)
    slaggy = (m.has("slaggy") or parent.has("slaggy")) and not cleans
    out = Work(form="ingot", material=parent.id, tier=parent.tier,
               traits=["slaggy"] if slaggy else [])
    plan.outputs = [(out, units)]
    plan.units = units
    plan.lead, plan.fuel, plan.flux = m, fm, xm
    plan.dc = m.dc
    plan.rank_in = max(x.rank for x in (m, fm, xm) if x is not None)
    plan.rank_out = parent.rank
    plan.working = list(m.working) + list(fm.working)
    plan.minutes = _minutes(plan, row, units)
    plan.yields = True
    plan.noun = "ingot"
    _slag_cap(plan, out)


def _match_recipe(ids: set[str], *, via: str = "") -> tuple[str, dict, dict] | None:
    found = _match_recipes(ids, via=via)
    return found[0] if found else None


def _match_recipes(ids: set[str], *, via: str = "") -> list[tuple[str, dict, dict]]:
    """Every alloy whose components are exactly these materials: (alloy id, recipe,
    {material id: part index}). Every part must be supplied and nothing else may be in
    the crucible; an `any` part is supplied by any one of its members. Several can match
    one set (copper and tin are bronze, bell bronze or pewter by their shares), and the
    windows decide which."""
    out = []
    for aid, r in (bench_rules().get("alloys") or {}).items():
        if str(r.get("via") or "") != via:
            continue
        parts = r.get("parts") or []
        assign: dict[str, int] = {}
        ok = True
        for mid in ids:
            hit = next((i for i, part in enumerate(parts)
                        if mid == part.get("id") or mid in (part.get("any") or [])), None)
            if hit is None:
                ok = False
                break
            assign[mid] = hit
        if ok and set(assign.values()) == set(range(len(parts))):
            out.append((aid, r, assign))
    return out


def _window_misses(recipe: dict, assign: dict, parts: list, total: int) -> list[str]:
    """Each part of a recipe whose share of the melt is outside its window, in words:
    "copper 81 to 92%" beside what the melt has."""
    out = []
    for i, part in enumerate(recipe.get("parts") or []):
        share = 100 * sum(n for p, n in parts if assign.get(p.material) == i) / total
        lo, hi = float(part.get("min", 0)), float(part.get("max", 100))
        if share + 1e-9 < lo or share - 1e-9 > hi:
            label = part.get("as") or (metal(part.get("id")) or Metal(id="", name=str(
                part.get("id")))).name.lower()
            out.append(f"{label} {lo:g} to {hi:g}% (the melt has {share:.0f}%)")
    return out


def _build_alloy(plan: ForgePlan, row: dict) -> None:
    parts = [(p, int(n)) for p, n in plan.slots.values()]
    if len({p.material for p, _ in parts}) < 2:
        plan.problems.append("Alloying combines metals: put two or more different metals "
                             "in the crucible.")
        return
    if len({p.material for p, _ in parts}) != len(parts):
        plan.problems.append("The same metal is in the crucible twice: put it in once, "
                             "with the count you want.")
        return
    total = sum(n for _, n in parts)
    ids = {p.material for p, _ in parts}
    if _match_recipe(ids, via="fold"):
        plan.problems.append("Pattern steel is folded, not melted: fold a steel bar with a "
                             "high-carbon steel bar.")
        return
    candidates = _match_recipes(ids)
    metal_units = sum(n for p, n in parts if p.form in BAR_FORMS)
    slag = any("slaggy" in p.traits for p, _ in parts)
    rules = bench_rules()
    found = next((c for c in candidates if not _window_misses(c[1], c[2], parts, total)),
                 None)
    if candidates and found is None:
        names = " and ".join(sorted(p.name.lower() for p, _ in parts))
        said = "; ".join(
            f"{(metal(aid).name if metal(aid) else aid).lower()} wants "
            + ", ".join(_window_misses(r, a, parts, total))
            for aid, r, a in candidates)
        plan.problems.append(f"No alloy of {names} pours at those shares: {said}.")
        return
    if found:
        aid, recipe, assign = found
        am = metal(aid)
        if am is None:
            plan.problems.append(f"The recipe names {aid}, which is not on the shelf.")
            return
        if not metal_units:
            plan.problems.append("Nothing in the crucible is an ingot or a bar.")
        if plan.problems:
            return
        out = Work(form="bar", material=am.id, tier=am.tier,
                   traits=["slaggy"] if slag else [])
        plan.lead = am
        plan.dc = am.dc
        plan.rank_out = am.rank
    else:
        if any(p.form not in BAR_FORMS for p, _ in parts):
            plan.problems.append("No recipe names that mix. A new alloy is made from "
                                 "ingots and bars of metal alone.")
            return
        mats = [metal(p.material) for p, _ in parts]
        for m in mats:
            if m.id in SOLITARY or m.parent in SOLITARY:
                others = ", ".join(sorted(x.name for x in mats if x is not m))
                plan.problems.append(
                    f"{m.name} works alone: melted together with {others} it is only dead "
                    f"metal — what makes it {m.name.lower()} does not survive the mixing.")
                return
        floor = float((rules.get("novel_alloy") or {}).get("min_share", 20))
        for p, n in parts:
            share = 100 * n / total
            if share + 1e-9 < floor:
                plan.problems.append(f"A new alloy needs each metal at {floor:g}% or more; "
                                     f"{p.name} is {share:.0f}%.")
        if plan.problems:
            return
        order = sorted(zip(parts, mats), key=lambda pm: (-pm[0][1], -pm[1].rank, pm[1].id))
        lead = order[0][1]
        top = max(m.rank for m in mats)
        tops = {m.id for m in mats if m.rank == top}
        step = int((rules.get("novel_alloy") or {}).get("rarity_step", 1))
        rank = min(len(wc.TIERS), top + (step if len(tops) >= 2 else 0))
        out = Work(form="bar", material=lead.id, tier=wc.TIERS[rank - 1],
                   alloy_of=[m.id for _, m in order[1:]],
                   traits=["slaggy"] if slag else [])
        plan.lead = lead
        plan.dc = max(m.dc for m in mats)
        plan.rank_out = rank
    units = plan.batch
    plan.consumes = [(p, n * units) for p, n in parts]
    plan.outputs = [(out, metal_units * units)]
    plan.units = units
    plan.rank_in = max(p.rank for p, _ in parts)
    plan.working = list(plan.lead.working)
    plan.minutes = _minutes(plan, row, metal_units * units)
    plan.noun = "bar"
    _slag_cap(plan, out)


def _build_forge(plan: ForgePlan, row: dict) -> None:
    bar = _piece(plan, "metal")
    fuel = _piece(plan, "fuel")
    if plan.problems:
        return
    info = shape_info(plan.shape)
    if info is None:
        plan.problems.append(
            "Pick what to forge from the list of weapons and armour."
            if not plan.shape else
            f"There is no {plan.shape!r} on the weapon or armour lists to forge.")
        return
    rule = from_base(info["id"])
    if rule and rule.get("takes") != "plate":
        # Studded leather is a leather base and its studs (owner Q1.3): there is nothing
        # of it to forge. The armored coat's lining plates ARE forged, so it passes.
        plan.problems.append(
            f"{info['name'].capitalize()} is finished from a leather base: there is nothing "
            f"to forge for it. Put the base and its {rule.get('takes', 'fittings')} on the "
            f"anvil at Assemble.")
        return
    units = plan.batch
    plan.shape, plan.gear = info["id"], info["gear"]
    m, fm = metal(bar.material), metal(fuel.material)
    src = bar.as_work()
    plate = info["gear"] != "weapon"
    out = Work(form="plate" if plate else "blank", material=src.material,
               passes=src.passes, shape=info["id"], gear=info["gear"],
               traits=[t for t in src.traits if t in ("slaggy", "hot_short")],
               alloy_of=list(src.alloy_of), tier=src.tier or m.tier)
    plan.consumes = [(bar, int(info["bars"]) * units),
                     (fuel, int(row.get("fuel_per_unit", 1)) * units)]
    plan.outputs = [(out, units)]
    plan.units = units
    plan.lead, plan.fuel = m, fm
    # The book's Craft DC for the item at Forge (plan §7), not the metal's: PF1e prices a
    # special material and leaves the DC alone.
    plan.dc = int(info["dc"])
    plan.rank_in = max(bar.rank, fm.rank)
    plan.rank_out = wc.tier_rank(out.tier)
    plan.working = list(m.working) + list(fm.working)
    plan.minutes = _minutes(plan, row, units, "minutes_plate" if plate else "minutes")
    plan.yields = True
    plan.noun = "plate" if plate else "blank"
    _slag_cap(plan, out)


def _single(plan: ForgePlan, row: dict, change) -> None:
    """Quench, temper and hone: one blank or plate in, the same piece out, changed."""
    p = _piece(plan, "piece")
    if plan.problems:
        return
    m = metal(p.material)
    out = p.as_work()
    extra = change(out)
    if plan.problems:
        return
    plan.consumes = [(p, 1)] + [(x, 1) for x in extra]
    plan.outputs = [(out, 1)]
    plan.units = 1
    plan.lead = m
    plan.dc = m.dc
    plan.rank_in = max([p.rank] + [x.rank for x in extra])
    plan.rank_out = wc.tier_rank(out.tier)
    plan.working = list(m.working)
    plan.minutes = _minutes(plan, row, 1)
    plan.noun = out.form
    _slag_cap(plan, out)


def _build_quench(plan: ForgePlan, row: dict) -> None:
    q = _piece(plan, "quenchant")

    def change(w: Work) -> list:
        w.quench = q.material
        w.worked.append("quench")
        # A quench leaves the steel brittle until it is tempered (plan §7, accepted
        # 2026-10-03: skipping Temper leaves a real flaw).
        if "brittle" not in w.traits:
            w.traits.append("brittle")
        return [q]

    if q is None:
        _piece(plan, "piece")
        return
    _single(plan, row, change)


def _build_temper(plan: ForgePlan, row: dict) -> None:
    def change(w: Work) -> list:
        w.traits = [t for t in w.traits if t != "brittle"]
        w.worked.append("temper")
        return []

    _single(plan, row, change)


def _build_hone(plan: ForgePlan, row: dict) -> None:
    def change(w: Work) -> list:
        w.worked.append("hone")
        return []

    _single(plan, row, change)


def _build_fold(plan: ForgePlan, row: dict) -> None:
    p = _piece(plan, "piece")
    other = _piece(plan, "with", optional=True)
    flux = _piece(plan, "flux", optional=True)
    if plan.problems:
        return
    m = metal(p.material)
    extra = [flux] if flux is not None else []
    if other is not None:
        pair = {p.material, other.material}
        found = _match_recipe(pair, via="fold") if len(pair) == 2 else None
        if found is None or p.form not in BAR_FORMS:
            plan.problems.append("Folding two bars together makes pattern steel, from a "
                                 "steel bar and a high-carbon steel bar.")
            return
        am = metal(found[0])
        out = Work(form="bar", material=am.id, tier=am.tier)
        plan.consumes = [(p, 1), (other, 1)] + [(x, 1) for x in extra]
        plan.lead = am
        plan.dc = am.dc
        plan.rank_out = am.rank
        plan.rank_in = max([p.rank, other.rank] + [x.rank for x in extra])
    else:
        out = p.as_work()
        if "slaggy" in out.traits:
            # Folding drives the slag out of dirty metal (pattern welding was a fix for
            # bloom iron, sweep §3.5) and adds nothing else to it.
            out.traits = [t for t in out.traits if t != "slaggy"]
        else:
            out.traits.append("folded")
        out.worked.append("fold")
        plan.consumes = [(p, 1)] + [(x, 1) for x in extra]
        plan.lead = m
        plan.dc = m.dc
        plan.rank_out = wc.tier_rank(out.tier)
        plan.rank_in = max([p.rank] + [x.rank for x in extra])
    plan.flux = metal(flux.material) if flux is not None else None
    plan.outputs = [(out, 1)]
    plan.units = 1
    plan.working = list(plan.lead.working) + (list(plan.flux.working) if plan.flux else [])
    plan.minutes = _minutes(plan, row, 1)
    plan.noun = out.form


def _build_strengthen(plan: ForgePlan, row: dict) -> None:
    bar = _piece(plan, "bar")
    flux = _piece(plan, "flux", optional=True)
    if plan.problems:
        return
    units = plan.batch
    per = int(row.get("bars_per_unit", 2))
    m = metal(bar.material)
    out = bar.as_work()
    out.form = "bar"
    out.passes = int(out.passes) + 1
    out.cut = 0
    out.worked = [w for w in out.worked if w != "fold"]
    plan.consumes = [(bar, per * units)]
    if flux is not None:
        plan.consumes.append((flux, units))
        plan.flux = metal(flux.material)
    plan.outputs = [(out, units)]
    plan.units = units
    plan.lead = m
    plan.dc = m.dc
    plan.rank_in = max(bar.rank, plan.flux.rank if plan.flux else 1)
    plan.rank_out = wc.tier_rank(out.tier)
    plan.working = list(m.working) + (list(plan.flux.working) if plan.flux else [])
    plan.minutes = _minutes(plan, row, units)
    plan.noun = "bar"
    _slag_cap(plan, out)


def masterwork_ready(w: Work | None) -> tuple[bool, str]:
    """Whether a main piece can carry Superior work (plan §7, "Masterwork chain"): it has
    been tempered (so it is not brittle) and, for an edged weapon, honed."""
    if w is None:
        return False, "there is no main piece"
    if "temper" not in w.worked or "brittle" in w.traits:
        return False, "the main piece is not tempered"
    if w.gear == "weapon" and _edged(w.shape) and "hone" not in w.worked:
        return False, "the blade is not honed"
    return True, ""


def _build_assemble(plan: ForgePlan, row: dict) -> None:
    gear = plan.gear or "weapon"
    names = PIECES[gear]
    main = _piece(plan, names[0])
    if main is None:
        return
    if main.base is not None:
        _build_from_base(plan, row, main)
        return
    for slot in names[1:REQUIRED_PIECES]:
        _piece(plan, slot)
    for slot in plan.slots:
        if slot not in names:
            plan.problems.append(f"A {_shape_name(main.work.shape).lower()} has no "
                                 f"{slot}.")
    fast = plan.slots.get("fastenings")
    if laced(main.work.shape) and fast and fast[0].form != "lacing":
        # Steel lamellar is steel plates laced together (owner, 2026-10-08 answer 1): the
        # leatherworker supplies the lacing set, as with a grip.
        plan.problems.append(f"{_a(_shape_name(main.work.shape).lower()).capitalize()} is "
                             f"laced: its fastenings are a leatherworker's lacing set, not "
                             f"{fast[0].name.lower()}.")
    if plan.problems:
        return
    head = main.work.copy()
    info = shape_info(head.shape) or {}
    pieces: dict[str, dict] = {}
    for slot in names:
        got = plan.slots.get(slot)
        if not got:
            continue
        p = got[0]
        w = p.work
        if p.leather is not None:
            pieces[slot] = _leather_spec(p)
            continue
        piece = {"material": p.material, "passes": int(w.passes) if w else 0}
        if slot == names[0]:
            if "folded" in head.traits:
                piece["folded"] = True
            if head.alloy_of:
                piece["alloy_of"] = list(head.alloy_of)
        elif w is not None and w.alloy_of:
            piece["alloy_of"] = list(w.alloy_of)
        pieces[slot] = piece
    ready, why = masterwork_ready(head)
    mw = _mw_index()
    plan.masterwork_work = bool(ready and plan.aim)
    plan.masterwork_why = why if not ready else ("" if plan.aim
                                                  else "you are not aiming for masterwork")
    m = metal(main.material)
    plan.dc = int(info.get("dc", m.dc))
    cap = plan.ceiling
    if head.quality is not None:
        # The finished item can rise one step above its main piece, no more (proposed:
        # a Crude blank does not become a Superior sword in one assembly).
        cap = min(cap, int(head.quality) + 1)
    if not plan.masterwork_work:
        cap = min(cap, mw - 1)
    elif plan.ceiling >= mw and not m.has("flawless"):
        # The book's masterwork component is DC 20 (CRB Craft); Unchained's `flawless`
        # raw material waives the increase.
        plan.dc = max(plan.dc, int(bench_rules().get("masterwork_dc", MASTERWORK_DC)))
    plan.step_ceiling = cap
    out = Work(form="item", material=head.material, shape=head.shape, gear=gear,
               quench=head.quench, pieces=pieces,
               traits=[t for t in head.traits if t in ("brittle", "hot_short", "slaggy")],
               smith={"level": plan.level,
                      "perks": {"potency": plan.perks.get("potency", 0),
                                "hardening": plan.perks.get("hardening", 0)}},
               tier=wc.TIERS[max(p.rank for p, _ in plan.slots.values()) - 1])
    plan.consumes = [(p, 1) for p, _ in plan.slots.values()]
    plan.outputs = [(out, 1)]
    plan.units = 1
    plan.lead = m
    # The smith's own pieces set the step's rarity; a leather grip or lacing set is the
    # tanner's work and is not gated by the smith's level (the item keeps its tier).
    forged = [p.rank for p, _ in plan.slots.values() if not p.from_leather] or [main.rank]
    plan.rank_in = max(forged)
    plan.rank_out = max(forged)
    plan.working = list(m.working)
    plan.minutes = _minutes(plan, row, 1)
    plan.noun = "item"
    plan.shape = head.shape
    if "slaggy" in head.traits:
        plan.step_ceiling = min(plan.step_ceiling, plan.ceiling - 1)


def _leather_spec(p: Piece) -> dict:
    """A record's piece for a leather grip or lacing set (leatherworking contracts §4.2):
    the hide's id and laminations, its form, grade and tannin, and a generic hide's beast,
    as the leather bench writes its own pieces (`leatherworker._piece_spec`)."""
    h = p.leather
    spec = {"material": p.material, "passes": int(getattr(h, "passes", 0) or 0),
            "form": p.form, "grade": int(getattr(h, "grade", 0) or 0)}
    if getattr(h, "tannage", ""):
        spec["tannage"] = str(h.tannage)
    if getattr(h, "creature", ""):
        spec["creature"] = str(h.creature)
    return spec


def _build_from_base(plan: ForgePlan, row: dict, main: Piece) -> None:
    """Assemble with a leatherworker's base as the body (leatherworking plan §4.3; owner
    Q1.3 and the 2026-10-08 answer 2). The base is consumed and its pieces kept; the forge
    fills the one slot its finish names (studs into the fastenings for studded leather,
    the forged plates into the lining for an armored coat) and the record's base becomes
    the finished suit. The quality is the LOWER of the base's and this Assemble's, so
    neither craft lifts the other's work: the step's ceiling is held at the base's tier.
    Masterwork follows the book (plan §13.4): Superior or better, or a body masterwork by
    nature, which `forge_items.build` reads off the body itself."""
    rec = main.base or {}
    base_q = int(rec.get("quality_index") if rec.get("quality_index") is not None else 1)
    finishes = [s for s in rec.get("base_for") or () if from_base(s)]
    filled = {}
    for s in finishes:
        rule = from_base(s)
        got = plan.slots.get(rule["slot"])
        if got and _finish_fits(got[0], s, rule) == "":
            filled[s] = rule
    want = str(plan.shape or "").strip().lower()
    if want and want not in finishes:
        # Asked for by name (the page sends a shape only at Forge; a request may send one
        # anywhere): a leather base becomes only what its maker made it a base for.
        plan.problems.append(
            f"{main.name} is a base for "
            + " or ".join(_shape_name(s).lower() for s in finishes)
            + f", not {_shape_name(want).lower()}.")
        return
    if want:
        shape = want
    elif len(filled) == 1:
        shape = next(iter(filled))
    else:
        plan.problems.append(
            f"{main.name} is the base for " + " or ".join(
                f"{_shape_name(s).lower()} ({_finish_words(s)})" for s in finishes) + ".")
        return
    rule = from_base(shape)
    slot = rule["slot"]
    got = plan.slots.get(slot)
    if not got:
        plan.problems.append(f"{_shape_name(shape).capitalize()} takes "
                             f"{_finish_words(shape)}.")
        return
    piece = got[0]
    why = _finish_fits(piece, shape, rule)
    if why:
        plan.problems.append(f"{piece.name}: {why}.")
    for other in plan.slots:
        if other not in ("body", slot):
            # The base keeps its own lacing and lining: the forge fills only its slot.
            plan.problems.append(f"The base keeps its own {other}: the forge fills only the "
                                 f"{slot} of {_a(_shape_name(shape).lower())}.")
    if plan.problems:
        return
    info = shape_info(shape) or {}
    pieces = _copy.deepcopy(rec.get("pieces") or {})
    w = piece.work
    spec = {"material": piece.material, "passes": int(w.passes) if w else 0}
    if w is not None and w.alloy_of:
        spec["alloy_of"] = list(w.alloy_of)
    pieces[slot] = spec
    m = metal(piece.material)
    mw = _mw_index()
    body_doc = metal(main.material)
    always = bool(body_doc is not None and body_doc.doc.get("always_masterwork") is True)
    ready = base_q >= mw or always
    plan.masterwork_work = bool(ready and plan.aim)
    plan.masterwork_why = (
        f"the base is {wc.quality_name(base_q)}: the finished suit is no better than its base"
        if not ready else ("" if plan.aim else "you are not aiming for masterwork"))
    plan.dc = int(info.get("dc", m.dc if m else 10))
    # The owner's rule: the lower of the base's tier and this Assemble's.
    cap = min(plan.ceiling, base_q)
    if not plan.masterwork_work:
        cap = min(cap, mw - 1)
    elif cap >= mw and not (m is not None and m.has("flawless")):
        plan.dc = max(plan.dc, int(bench_rules().get("masterwork_dc", MASTERWORK_DC)))
    plan.step_ceiling = cap
    smith = rec.get("smith") or rec.get("maker") or {}
    out = Work(form="item", material=main.material, shape=shape, gear="armour",
               quench=w.quench if w is not None else "", pieces=pieces,
               traits=[t for t in (w.traits if w is not None else [])
                       if t in ("brittle", "hot_short", "slaggy")],
               smith={"level": plan.level,
                      "perks": {"potency": plan.perks.get("potency", 0),
                                "hardening": plan.perks.get("hardening", 0)}},
               tier=wc.TIERS[max(main.rank, piece.rank) - 1],
               from_base={"id": str(rec.get("id") or ""), "name": main.name,
                          "craft": str(rec.get("craft") or "leatherworker"),
                          "quality": base_q,
                          "level": int((smith or {}).get("level", 1) or 1)})
    plan.consumes = [(main, 1), (piece, 1)]
    plan.outputs = [(out, 1)]
    plan.units = 1
    plan.lead = m
    plan.rank_in = piece.rank
    plan.rank_out = piece.rank
    plan.working = list(m.working) if m is not None else []
    plan.minutes = _minutes(plan, row, 1)
    plan.noun = "item"
    plan.gear, plan.shape = "armour", shape


def _finish_words(shape: str) -> str:
    rule = from_base(shape) or {}
    if rule.get("takes") == "studs":
        return f"studs in the {rule.get('slot', 'fastenings')}"
    return f"its forged plates in the {rule.get('slot', 'lining')}"


def _finish_fits(p: Piece, shape: str, rule: dict) -> str:
    """Why this piece cannot be what the forge adds to a base for this suit, or ""."""
    takes = rule.get("takes")
    if takes == "studs":
        if p.work is None and not p.from_leather and p.material in stud_ids():
            return ""
        return (f"{_shape_name(shape).lower()} is studded with "
                + " or ".join(n.lower() for n in
                              [(metal(x).name if metal(x) else x) for x in stud_ids()]
                              or ["metal studs"]))
    if takes == "plate":
        if p.form == "plate" and p.work is not None and p.work.shape == shape:
            return ""
        return f"{_a(_shape_name(shape).lower())} is lined with plates forged for it"
    return "the forge adds nothing to this base"


def _build_finish(plan: ForgePlan, row: dict) -> None:
    item = _piece(plan, "item")
    tr = _piece(plan, "treatment")
    if plan.problems:
        return
    rules = bench_rules()
    w = item.work.copy()
    tm = metal(tr.material)
    sacred = set(rules.get("sacred_finishes") or [])
    if tm.id in sacred and plan.level < int(rules.get("sacred_level", 3)):
        plan.problems.append(f"{tm.name} is a sacred finish, learned at Blacksmith "
                             f"{int(rules.get('sacred_level', 3))}.")
    if tm.id in w.finish:
        plan.problems.append(f"It already carries {tm.name.lower()}.")
    law = (rules.get("finish_rules") or {}).get(tm.id) or {}
    main = (w.pieces.get(PIECES.get(w.gear, PIECES["weapon"])[0]) or {}).get("material", "")
    main_m = metal(main)
    if main and (main in (law.get("not_on") or [])
                 or (main_m is not None and main_m.parent in (law.get("not_on") or []))):
        plan.problems.append(f"{tm.name} will not take on "
                             f"{(main_m.name if main_m else main).lower()}.")
    if law.get("gear") and w.gear not in law["gear"]:
        plan.problems.append(f"{tm.name} goes on "
                             f"{' or '.join(g for g in law['gear'])}, not this.")
    if plan.problems:
        return
    w.finish.append(tm.id)
    plan.consumes = [(item, 1), (tr, 1)]
    plan.outputs = [(w, 1)]
    plan.units = 1
    plan.lead = tm
    plan.dc = tm.dc
    plan.rank_in = max(item.rank, tm.rank)
    plan.rank_out = max(wc.tier_rank(w.tier), tm.rank)
    plan.working = list(tm.working)
    plan.minutes = _minutes(plan, row, 1)
    plan.noun = "item"
    plan.gear, plan.shape = w.gear, w.shape
    # A finish does not re-grade the item: its quality was earned at Assemble.
    plan.step_ceiling = plan.ceiling


_BUILD = {"smelt": _build_smelt, "alloy": _build_alloy, "forge": _build_forge,
          "quench": _build_quench, "temper": _build_temper, "fold": _build_fold,
          "hone": _build_hone, "assemble": _build_assemble, "finish": _build_finish,
          "strengthen": _build_strengthen}


def make(plan: ForgePlan, tier: int, *, extra: int = 0) -> list[tuple[Work, int]]:
    """What a finished step puts on the shelf, at the tier the player's hands earned.

    `extra` is the Yield perk's one more ingot or blank, rolled by the caller and shown
    (plan §4.2). A Crude result over a sulfurous fuel picks up a `hot_short` flaw unless
    the fuel burns clean (plan §5.5). A Finish leaves the item's quality alone.
    """
    tier = max(0, min(int(tier), plan.step_ceiling))
    out = []
    for i, (template, n) in enumerate(plan.outputs):
        w = template.copy()
        if plan.method != "finish":
            w.quality = tier
        if plan.method in ("smelt", "forge") and tier == 0 and plan.fuel is not None \
                and plan.fuel.has("sulfurous") and not plan.fuel.has("clean_heat") \
                and "hot_short" not in w.traits:
            w.traits.append("hot_short")
        w.name = ""
        w.name = work_name(w)
        out.append((w, int(n) + (int(extra) if i == 0 and plan.yields else 0)))
    return out


def land(actor, made: list[tuple[Work, int]]) -> list[tuple[str, Work, int]]:
    """Put what a step made on the shelf. A finished item whose name another, different
    build already holds is numbered ("Fine Iron Longsword (2)"), so wielding it by name
    and lane B's lookup by record id can never pick up the wrong one."""
    landed = []
    for w, n in made:
        if w.form == "item":
            base, k = w.name, 1
            while True:
                w.rid = _slug(w.name)
                key = stock_key(w)
                clash = any(st.name == w.name and sid != key
                            for sid, st in (actor.stock or {}).items())
                if not clash:
                    break
                k += 1
                w.name = f"{base} ({k})"
        landed.append((put(actor, w, n), w, n))
    return landed


def failure_losses(plan: ForgePlan, miss: int) -> list[tuple[Piece, int]]:
    """What a failed roll ruins, by the book's Craft rule as the plan states it (§11):
    miss by 4 or less and only the time is lost; miss by 5 or more and half of what was
    on the anvil is ruined, rounded down, which is at least one whenever there were two.
    A `malleable` main metal ruins nothing (Pathfinder Unchained).

    Shared out by each material's share, largest remainders first; a tie goes to the
    cheaper thing (raw fuel and quenchant before worked pieces, then the lower rarity).
    Every smithing minigame that shipped was softened afterwards (sweep §1), so the
    forge starts on the generous side of a tie: a failed quench by 5 spoils the bath, not
    the blank."""
    if miss < 5 or (plan.lead is not None and plan.lead.has("malleable")):
        return []
    total = sum(int(n) for _, n in plan.consumes)
    ruin = total // 2
    if ruin <= 0:
        return []
    shares = []
    for i, (p, n) in enumerate(plan.consumes):
        exact = n * ruin / total
        # A leather base or grip is worked stock too, so a tie spoils the studs first.
        worked = 1 if (p.work is not None or p.from_leather) else 0
        shares.append([p, int(exact), exact - int(exact), n, (worked, p.rank, i)])
    left = ruin - sum(s[1] for s in shares)
    for s in sorted(shares, key=lambda s: (-round(s[2], 9), s[4])):
        if left <= 0:
            break
        if s[1] < s[3]:
            s[1] += 1
            left -= 1
    return [(p, k) for p, k, _, _, _ in shares if k > 0]


def spend(actor, consumes: list[tuple[Piece, int]]) -> list[dict]:
    """Take what a step used: raw material from the satchel's counts, products off the
    shelf, by the key the rack was read under."""
    out = []
    for p, n in consumes:
        if n <= 0:
            continue
        if p.key.startswith("stock:"):
            took = actor.take_stock(p.key.split(":", 1)[1], n)
        else:
            took = actor.spend(p.material, n)
        if took:
            out.append({"key": p.key, "name": p.name, "count": int(took)})
    return out


def tuning_for(plan: ForgePlan) -> dict:
    """The minigame's numbers (UI plan §9): the method's base difficulty, harder by
    `rarity_step` per band above common (better metal, tighter window: Giants' Foundry),
    and the working traits' band scales (forgiving wider, narrow_window narrower,
    quench_sensitive only at the quench, weld_aid only when welding). The same at every
    level: skill raises the ceiling, not the window, as for herbs."""
    rules = bench_rules()
    row = method_row(plan.method) or {}
    tun = row.get("tuning") or {}
    traits = rules.get("traits") or {}
    band = 1.0
    for t in dict.fromkeys(plan.working):
        spec = traits.get(t) or {}
        band *= float(spec.get("band", 1.0))
        if plan.method == "quench":
            band *= float(spec.get("quench_band", 1.0))
        if plan.method in ("fold", "strengthen"):
            band *= float(spec.get("weld_band", 1.0))
    rank = plan.lead.rank if plan.lead is not None else 1
    diff = float(tun.get("difficulty", 0.45)) + float(rules.get("rarity_step", 0.05)) \
        * max(0, rank - 1)
    ceiling = max(0, int(plan.step_ceiling))
    return {"method": plan.method, "game": plan.method,
            "difficulty": round(min(0.95, diff), 4), "band_scale": round(band, 4),
            "band": tun.get("band", ""), "seconds": tun.get("seconds", 6),
            "traits": list(dict.fromkeys(plan.working)),
            "reheat_minutes": int(rules.get("reheat_minutes", 5)),
            "names": [wc.quality_name(t) for t in range(ceiling + 1)],
            "bands": [t / (ceiling + 1) for t in range(ceiling + 1)],
            "masterwork_at": _mw_index()}


# --- assay (lane E, contracts §6) --------------------------------------------------------

def assay_source(actor, material_id: str) -> Piece | None:
    """What a sliver for assaying this material would come from: a bar or ingot of it
    first (a tenth is cut), else ore or any raw unit of it (one is used)."""
    mid = str(material_id or "").strip().lower()
    # Leather stock is never cut for a sliver at the forge: a hide is graded at the leather
    # bench (lane F's Grade), and a grip is not a bar.
    items = [p for p in rack(actor) if p.material == mid and not p.old and not p.from_leather
             and p.form not in PIECE_FORMS + ("item",)]
    # A bar already cut into is cut again before a whole one is started, or two assays
    # would leave two part-bars on the rack.
    bars = sorted((p for p in items if p.form in BAR_FORMS and (p.count > 0 or p.cut)),
                  key=lambda p: (not p.cut, p.key))
    return (bars or [p for p in items if p.count > 0] or [None])[0]


def cut_sliver(actor, p: Piece, tenths: int = 1) -> dict:
    """Cut tenths of a bar off a carried bar (plan §9.2: "bars track tenths"). A raw bar
    from the satchel becomes a forge bar on the shelf the first time it is cut."""
    tenths = max(1, int(tenths))
    if p.key.startswith("inv:"):
        actor.spend(p.material, 1)
        w = p.as_work()
        w.cut = tenths
        key = put(actor, w, 1)
        return {"key": f"stock:{key}", "name": p.name, "tenths": tenths}
    sid = p.key.split(":", 1)[1]
    st = actor.stock.get(sid)
    w = Work.from_stock(st)
    w.cut = int(w.cut) + tenths
    while w.cut >= 10:
        actor.take_stock(sid, 1)
        w.cut -= 10
    st = actor.stock.get(sid)
    if st is not None:
        st.properties = w.tags()
    return {"key": p.key, "name": p.name, "tenths": tenths}


def pay_assay(actor, material_id: str, cost: dict) -> list[dict]:
    """Take what lane E's assay says it cost: `{"bars": 0.1}` cuts a tenth of a bar,
    `{"ore": 1}` (or any other count) uses whole units of the material."""
    p = assay_source(actor, material_id)
    if p is None:
        return []
    cost = dict(cost or {})
    if "bars" in cost and p.form in BAR_FORMS:
        return [cut_sliver(actor, p, int(round(float(cost["bars"]) * 10)) or 1)]
    n = int(next((v for k, v in cost.items() if k != "bars"), 1) or 1)
    return spend(actor, [(p, max(1, n))])


def working_keys(doc: dict) -> list[str]:
    """The knowledge keys of a material's working traits, revealed by working it (plan
    §9.2: "you watched it behave"). Lane E's `working_keys` when it offers one; else read
    from `property_keys` assuming its order is weapon effects, armour effects, working
    traits, quench mark (contracts §6 says one positional key per effect and working
    trait, "as today")."""
    kn = _lane("knowledge")
    if kn is None:
        return []
    fn = getattr(kn, "working_keys", None)
    if fn is not None:
        return list(fn(doc))
    keys = list(kn.property_keys(doc))
    n_fx = len(doc.get("weapon") or []) + len(doc.get("armour") or [])
    return keys[n_fx:n_fx + len(doc.get("working") or [])]


def reveal(actor, material_id: str, keys, how: str) -> list[str]:
    """Record keys as known; returns the new ones. Lane E's `reveal` when it has one, else
    the herbarium's own (one store, `Actor.herb_known`, contracts §6)."""
    kn = _lane("knowledge")
    fn = getattr(kn, "reveal", None) if kn is not None else None
    if fn is None:
        from . import herbknowledge

        fn = herbknowledge.reveal
    return list(fn(actor, material_id, list(keys), how) or [])
