"""Alchemy chains: what a set of materials and a sequence of laboratory verbs produces.

The Herbalist's nearest sibling, and deliberately shaped like `rules/crafting.py` — the
same public surface (`TRACK_ID`, `CraftError`, `Chain`, `chain_from_body`, `check_terms`,
`check_bonus`, `preview`, `materials`) so the shared bench can dispatch to whichever craft
owns a chain without learning two vocabularies. The *methods* do not overlap: herbalism
owns grind/brew/distill/infuse/purify, and this module owns the laboratory's verbs —
calcine, dissolve, filter, precipitate, react, sublime, catalyze, stabilize, seal.

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
stakes, and the numbers are itemised in the preview the same way `check_terms` itemises
the bonus — a player who can see the terms can see what would improve them.

**Potions that hold spells.** The trade's real product is not acid, it is a spell in a
bottle. `content/materials/alchemist-spell-potions.json` holds 44 hand-converted 1st-3rd
level spells, and a chain that matches one produces an item carrying `holds_spell`: the
cross-craft contract that says *this bottle stands in for knowing that spell*. Every
`spell` id in that file is verified against `content/spells/spells.json` by test, because
a potion of a spell the app has never heard of is the "ground every name" failure.
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

# One glyph per kind, from this track's reserved pool. Herbalism owns 🌿🍄🦴☠️ and none
# of those appear here: the shelf is shared between four crafts now, so a repeated glyph
# would make two different things look like the same thing on one page.
KIND_GLYPH = {
    "reagent": "🜂",        # the alchemical sign for fire: the working substance
    "solvent": "🧪",        # the flask a thing is taken up in
    "salt": "🧂",
    "catalyst": "💠",       # unchanged by the reaction it drives
    "essence": "🔆",
    "gland": "🩸",          # it came off something that was alive
    "vessel": "🫙",
    "treatment": "🧫",
    "intermediate": "🧊",   # another craft's product, arriving as a reagent
    "potion": "⚱️",         # what a matched spell-potion chain puts on the shelf
}


# --- materials -----------------------------------------------------------------------------


@dataclass
class Material:
    """One thing on the alchemist's shelf. The same shape as `ingredients.Ingredient`
    where the fields mean the same thing, plus the flags that are alchemy's own:
    `volatile` (counts toward the DC surcharge and the two-in-a-vessel rule),
    `needs_stabilizer` (attacks its own vessel — alkahest, phlogiston, a starfall core),
    and `obtain` (how the thing is come by, which the craft-action excursion reads)."""
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
    # How the thing is come by: "bought" | "mined" | "gathered" | "harvested", with
    # `market`/`price_gp`, `biomes` or `from_creatures` beside it. Authored per material
    # rather than derived from `kind`, because where a thing comes from is a fact about
    # the thing — a heuristic on kind would have said "buy a basilisk eye at the
    # apothecary".
    #
    # Flat, because all four crafts share `content/materials` and the other three landed
    # on the flat shape. One hub reads the whole shelf, and the odd one out conforms
    # rather than making the hub learn two shapes.
    obtain: str = ""
    market: str = ""
    price_gp: int | None = None
    biomes: list[str] = field(default_factory=list)
    # Singular *and* plural: the leatherworker writes `from_creatures` and the enchanter
    # writes `from_creature` for its 17 single-source entries. Reading both here means
    # the excursion matches every craft's shelf instead of silently skipping one.
    from_creatures: list[str] = field(default_factory=list)
    obtain_dc: int | None = None

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def glyph(self) -> str:
        return KIND_GLYPH.get(self.kind, "🜂")

    @property
    def obtain_how(self) -> str:
        return self.obtain

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
            "needs_stabilizer": self.needs_stabilizer, "glyph": self.glyph,
            "obtain": self.obtain, "market": self.market, "price_gp": self.price_gp,
            "biomes": self.biomes, "from_creatures": self.from_creatures,
            "obtain_dc": self.obtain_dc,
            "effects": self.effects, "lines": self.lines,
        }


def from_dict(d: dict) -> Material:
    # A sibling craft, or an older homebrew file, may nest the acquisition fields inside
    # `obtain` instead of writing them flat. Both are read rather than one being declared
    # correct: the shelf is shared, and a shape mismatch used to be a hard ValueError on
    # every chain the moment another craft's catalogue landed in the directory.
    raw = d.get("obtain")
    nested = raw if isinstance(raw, dict) else {}
    how = str(nested.get("how") if nested else (raw or ""))
    creatures = (d.get("from_creatures") or nested.get("from_creatures")
                 or ([d["from_creature"]] if d.get("from_creature") else []))
    return Material(
        id=d["id"], name=d.get("name", d["id"]), kind=d.get("kind", "reagent"),
        tier=d.get("tier", "common"), craft_dc=d.get("craft_dc"),
        text=d.get("text", ""), risky=bool(d.get("risky")),
        volatile=bool(d.get("volatile")),
        needs_stabilizer=bool(d.get("needs_stabilizer")),
        effects=list(d.get("effects") or []),
        effects_converted=bool(d.get("effects_converted")),
        obtain=how,
        market=str(d.get("market") or nested.get("market") or ""),
        price_gp=_int_or_none(d.get("price_gp", nested.get("price_gp"))),
        biomes=[str(b) for b in (d.get("biomes") or nested.get("biomes") or [])],
        from_creatures=[str(c) for c in creatures],
        obtain_dc=_int_or_none(d.get("obtain_dc", nested.get("dc"))),
    )


def _int_or_none(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_dir(path: str | Path, key: str) -> dict[str, dict]:
    """Raw entries from a directory, as dicts so they can be merged before being built.

    Two shapes, for the same reason `ingredients.load_dir` takes two: a shipped catalogue
    is one file holding a list under `key`, and a homebrew editor will write one file per
    thing it edits. A file holding some *other* craft's list is skipped rather than
    guessed at — `content/materials` is one shelf shared by four benches now, and the
    spell-potion catalogue lives there too under its own key.
    """
    out: dict[str, dict] = {}
    for p in sorted(Path(path).glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries = data.get(key) if isinstance(data, dict) else None
        if not isinstance(entries, list):
            entries = [data] if isinstance(data, dict) and data.get("id") else []
        for raw in entries:
            if isinstance(raw, dict) and raw.get("id"):
                out[raw["id"]] = raw
    return out


def load_dir(path: str | Path) -> dict[str, dict]:
    return _load_dir(path, "materials")


_MATERIALS: dict[str, Material] | None = None
_POTIONS: dict[str, "SpellPotion"] | None = None


def _homebrew(kind: str) -> Path:
    from django.conf import settings

    return Path(settings.CAMPAIGN_DIR).parent / "homebrew" / kind


def materials() -> dict[str, Material]:
    """Every material the bench knows, shipped and homebrew.

    Homebrew is layered over the shipped set rather than replacing it, so a corrected
    catalogue in a later build is not shadowed by a stale copy in the user's data
    directory — the trap `CLAUDE.md` records from World Bible's stylesheet, and the
    exact pattern `worldclass.tracks()` uses for the same reason.

    Shelf-wide, not track-wide: `content/materials` holds all four crafts' catalogues,
    and an alchemist who wants the leatherworker's cured leather for a potion of mage
    armour should be able to reach for it.
    """
    global _MATERIALS
    if _MATERIALS is None:
        from django.conf import settings

        raw = load_dir(Path(settings.BASE_DIR) / "content" / "materials")
        user = _homebrew("materials")
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

    An infusion is a reagent: the crafts are meant to feed each other, and a "Woundwort
    Tincture" is exactly the kind of prepared liquid a reaction wants as its medium.
    Recognised by id shape — the slug ends with (or contains) one of herbalism's shape
    words, optionally carrying crafting.Stock's "#concentration" suffix — because the id
    is the only thing a chain hands us, and the shape word is the one part of it the
    other craft guarantees.

    Tier defaults to common: the id does not carry the jar's tier, and guessing higher
    would let an id string bypass the tier gate that real stock is checked against.
    """
    slug = str(material_id or "").split("#")[0].strip().lower()
    if not slug:
        return None
    if not any(slug.endswith(word) or f"-{word}-" in f"-{slug}-"
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


# --- acquisition ----------------------------------------------------------------------------
#
# The craft-action button is becoming the single hub for *obtaining* materials, replacing
# the foraging panel inside the crafting menu. What each excursion offers is data here so
# the UI stays one screen: the page asks what the track offers, not what alchemy is.

ACQUISITION: dict[str, dict] = {
    "market-run": {
        "id": "market-run",
        "label": "Buy reagents",
        "obtain": "bought",
        "needs": "market",
        # The markets the catalogue actually names, so the page can offer the right list
        # rather than every reagent in the world at every stall.
        "markets": ["market", "apothecary", "glassblower", "smith", "temple",
                    "planar broker"],
        "blurb": "An apothecary sells brimstone and lamp oil; a planar broker sells "
                 "azoth and asks no questions. Price is in gp on each material.",
    },
    "quarry": {
        "id": "quarry",
        "label": "Mine salts and ores",
        "obtain": "mined",
        "needs": "biome",
        "blurb": "Vitriol out of a cave wall, brimstone from a fumarole, star-iron from "
                 "a crater. Needs the right ground under you and a check against the "
                 "material's DC.",
    },
    "field-gathering": {
        "id": "field-gathering",
        "label": "Gather field reagents",
        "obtain": "gathered",
        "needs": "biome",
        "blurb": "Pitch from a pine, natron from a dry lakebed, ghost salt from a crypt "
                 "cistern. The alchemist's answer to foraging, and the reason this "
                 "track has no forage panel of its own.",
    },
    "harvest-reagents": {
        "id": "harvest-reagents",
        "label": "Harvest reagents from a kill",
        "obtain": "harvested",
        "needs": "creature",
        "blurb": "The gland, sac or humour comes off something that was alive, and the "
                 "creature has to have been in the scene. An ankheg acid sac should come "
                 "from an ankheg the table actually killed.",
    },
}


def obtainable(obtain_kind: str, *, biome: str = None,
               creature: str = None) -> list[Material]:
    """Every material one excursion could turn up, filtered by where the party is.

    Shelf-wide on purpose: a market sells what the market sells regardless of which
    bench wanted it, and one shared shelf was the point of moving all four catalogues
    into `content/materials`. Only materials that *declare* an `obtain` are returned, so
    a sibling craft's entry appears here the moment it declares one and not before —
    silence is treated as "not stated", never as "buy it anywhere".

    Creature matching is substring-and-case-insensitive in both directions, because the
    scene names a creature "the ankheg" and the material names "ankheg".
    """
    want = str(obtain_kind or "").strip().lower()
    said = str(creature or "").strip().lower()
    out: list[Material] = []
    for m in materials().values():
        if m.obtain_how != want:
            continue
        if biome and m.biomes and biome not in m.biomes:
            continue
        if said and m.from_creatures:
            if not any(c.lower() in said or said in c.lower()
                       for c in m.from_creatures):
                continue
        elif said and not m.from_creatures:
            continue
        out.append(m)
    return sorted(out, key=lambda m: (m.rank, m.name))


# --- potions that hold spells ---------------------------------------------------------------


@dataclass
class SpellPotion:
    """One recipe that puts a spell in a bottle.

    The `spell` id is the contract: it resolves in `content/spells/spells.json`, it rides
    out on the finished item as `holds_spell`, and the enchanter reads it to decide that
    a potion of X stands in for knowing X. Nothing else in the item identifies the spell,
    so nothing else may be renamed.
    """
    id: str
    name: str
    spell: str
    spell_level: int = 1
    caster_level: int = 1
    tier: str = "uncommon"
    duration_text: str = ""
    how: list[str] = field(default_factory=lambda: ["drink"])
    materials: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    text: str = ""
    effects: list = field(default_factory=list)

    @property
    def rank(self) -> int:
        return wc.tier_rank(self.tier)

    @property
    def specs(self) -> list[dict]:
        return [{**dict(e), "from": dict(e).get("from") or self.name}
                for e in self.effects]

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "spell": self.spell,
            "spell_level": self.spell_level, "caster_level": self.caster_level,
            "tier": self.tier, "rank": self.rank, "duration_text": self.duration_text,
            "how": self.how, "materials": self.materials, "methods": self.methods,
            "text": self.text, "effects": self.effects, "glyph": KIND_GLYPH["potion"],
        }


def spell_potion_from_dict(d: dict) -> SpellPotion:
    return SpellPotion(
        id=d["id"], name=d.get("name", d["id"]), spell=d.get("spell", ""),
        spell_level=int(d.get("spell_level", 1)),
        caster_level=int(d.get("caster_level", 1)),
        tier=d.get("tier", "uncommon"), duration_text=d.get("duration_text", ""),
        how=list(d.get("how") or ["drink"]),
        materials=list(d.get("materials") or []),
        methods=list(d.get("methods") or []),
        text=d.get("text", ""), effects=list(d.get("effects") or []),
    )


def spell_potions() -> dict[str, SpellPotion]:
    """Every spell-potion recipe, shipped and homebrew, layered the same way materials
    are — a homebrew potion just works, and a corrected shipped one is not shadowed."""
    global _POTIONS
    if _POTIONS is None:
        from django.conf import settings

        raw = _load_dir(Path(settings.BASE_DIR) / "content" / "materials", "potions")
        user = _homebrew("materials")
        if user.is_dir():
            raw.update(_load_dir(user, "potions"))
        _POTIONS = {k: spell_potion_from_dict({**v, "id": k}) for k, v in raw.items()}
    return _POTIONS


def spell_potion(potion_id: str) -> SpellPotion:
    p = spell_potions().get((potion_id or "").strip().lower())
    if p is None:
        raise KeyError(f"no spell potion {potion_id!r}")
    return p


def _potion_for(material_ids: list[str], methods: list[str]) -> SpellPotion | None:
    """The spell potion this chain brews, or None.

    Matched on the exact set of materials *and* the exact method sequence. Strict on
    purpose: a near-match would quietly hand the player a different potion from the one
    they built, and "you got a potion of blur because you were one reagent short of
    invisibility" is a bug report nobody could write. The recipe is the recipe.
    """
    want = sorted({str(m).strip().lower() for m in material_ids})
    seq = [str(m).strip().lower() for m in methods]
    for potion in spell_potions().values():
        if sorted({m.lower() for m in potion.materials}) == want \
                and [m.lower() for m in potion.methods] == seq:
            return potion
    return None


# --- chains --------------------------------------------------------------------------------


@dataclass
class Chain:
    """An ordered list of laboratory verbs applied to a set of materials — the chain is
    the thing that gets validated, not a recipe. Same shape as `crafting.Chain` minus
    the track field, because this module only ever speaks for one track."""
    methods: list[str] = field(default_factory=list)
    material_ids: list[str] = field(default_factory=list)
    name: str = ""
    # Crafted things going back on the bench, as {stock id: how many}. Kept apart from
    # raw materials for the reason crafting.Chain keeps them apart: these are *spent*
    # from a finite shelf, where the reagent list is a request.
    stock_used: dict[str, int] = field(default_factory=dict)

    @property
    def stages(self) -> int:
        return len(self.methods)

    @property
    def every_material(self) -> list[str]:
        """Raw materials and crafted inputs together, which is what the rules actually
        judge: a reaction does not care whether its medium came off a shelf or out of a
        still."""
        out = list(self.material_ids)
        for sid, n in self.stock_used.items():
            out.extend([sid] * max(0, int(n)))
        return out


def chain_from_body(body: dict) -> Chain:
    """A chain out of a request body, tolerant of every key being absent.

    The bench posts a form and the dispatcher hands the body straight here, so this is
    where a missing key becomes an empty list rather than a 500. A chain with nothing in
    it is a legal object that `preview` will refuse in words — which is the whole
    contract: bad chains come back as `problems`, never as exceptions.
    """
    body = body or {}
    methods = body.get("methods") or []
    mats = body.get("materials") or body.get("material_ids") or []
    if isinstance(methods, str):
        methods = [m for m in methods.replace(",", " ").split() if m]
    if isinstance(mats, str):
        mats = [m for m in mats.replace(",", " ").split() if m]
    stock = body.get("stock") or body.get("stock_used") or {}
    if not isinstance(stock, dict):
        stock = {str(s): 1 for s in stock}
    return Chain(
        methods=[str(m).strip().lower() for m in methods if str(m).strip()],
        material_ids=[str(m).strip().lower() for m in mats if str(m).strip()],
        name=str(body.get("name") or "").strip(),
        stock_used={str(k): int(v) for k, v in stock.items() if int(v or 0) > 0},
    )


def check_terms(actor, level: int) -> list[dict]:
    """What an alchemist adds to the die, itemised.

    **d20 + track level + half character level + Intelligence.** The same shape as
    `crafting.check_terms`, with Int where herbalism uses Wis: Craft is an
    Intelligence-based skill in PF1e and alchemy is the Craft skill the trade is named
    for, where herbalism's fieldwork leans on Wisdom. That one substitution is the only
    difference, and it is why an alchemist and a herbalist are different characters
    rather than the same character with two shelves.

    Itemised rather than summed because the sum is the boring half: "+9" says nothing,
    "Alchemist 4, half level +3, Int +2" says which of the three to go and improve.
    """
    track_level = max(0, int(level or 0))
    char_level = max(1, int(getattr(actor, "level", 1) or 1)) if actor else 1
    intelligence = int(actor.ability_mod("int")) if actor is not None else 0
    return [
        {"label": f"Alchemist {track_level}", "value": track_level},
        # Half level, rounded down, as every half-level term in 1e rounds.
        {"label": f"half character level ({char_level})", "value": char_level // 2},
        {"label": "Intelligence", "value": intelligence},
    ]


def check_bonus(actor, level: int) -> int:
    return sum(t["value"] for t in check_terms(actor, level))


def _chance(dc: int, bonus: int, problems: list[str] = ()) -> int:
    """Percent chance the check makes the DC, for the label on the button.

    Clamped to 5-95 because a natural 1 always fails and a natural 20 always succeeds,
    so no craft is ever certain either way and the number should not claim otherwise.
    """
    if problems:
        return 0
    need = dc - bonus
    return max(5, min(95, int(round(100 * (21 - need) / 20))))


@dataclass
class Result:
    name: str
    tier: str
    rank: int
    stages: int
    potency: float
    dc: int
    # The DC itemised, the way `check_terms` itemises the bonus: "+3 second volatile" is
    # a sentence the player can act on, and a bare 19 is one they must trust.
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
    # What the successful craft puts on the shelf, and what it takes off.
    output: dict | None = None
    consumes: dict[str, int] = field(default_factory=dict)
    # The crafter's own bonus on this chain and what it is made of, present only when an
    # actor was passed — a preview with no actor is the bench asking "is this legal",
    # not "will I make it".
    bonus: int = 0
    terms: list[dict] = field(default_factory=list)
    chance: int = 0

    def as_dict(self) -> dict:
        return {
            "name": self.name, "tier": self.tier, "rank": self.rank,
            "stages": self.stages, "potency": round(self.potency, 2),
            "dc": self.dc, "dc_terms": self.dc_terms, "volatiles": self.volatiles,
            "mishap": self.mishap, "risky": self.risky, "cleansed": self.cleansed,
            "effects": self.effects, "drawbacks": self.drawbacks, "specs": self.specs,
            "removed": self.removed, "problems": self.problems,
            "materials": self.materials, "output": self.output,
            "consumes": self.consumes, "bonus": self.bonus, "terms": self.terms,
            "chance": self.chance,
        }


def _slug(text: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in str(text).lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out


def _how_for(mats: list[Material], specs: list[dict]) -> list[str]:
    """Drink it, throw it, or paint it on a blade.

    Read off what is in the vessel rather than declared per recipe, because the same
    rule has to answer for a chain nobody wrote down. **A vessel is what makes a thing
    throwable** — the flask is the delivery, which is why alchemist's fire lists a clay
    flask and alchemical grease does not. So: harmful in a vessel is a splash weapon;
    harmful without one is a coating; anything that is not harmful is drunk.
    """
    harmful = any(str(s.get("type")) in con.HARMFUL for s in specs)
    if not harmful:
        return ["drink"]
    return ["throw"] if any(m.kind == "vessel" for m in mats) else ["coat"]


def preview(level: int, chain: Chain, stock: dict | None = None,
            actor=None) -> Result:
    """What this chain would make, and what could go wrong, without rolling anything.

    Mirrors `crafting.preview`'s contract: never raises for a chain that is merely bad —
    every refusal comes back in `problems` so the page can grey the button and say why.
    `stock` is what the character is carrying, as {material id: count}; passing None
    means "assume they have it", which is what the chain-rule tests want. `actor` adds
    the crafter's own bonus, terms and percentage; without one the preview answers "is
    this legal" rather than "will I make it".
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
    for mid in chain.every_material:
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
    effects = [f"{s.get('from')}: {effectspec.render(s)}" for s in sorted_out.benefits]
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

    # A matched recipe replaces what the materials would have said on their own: the
    # potion IS the spell, not the sum of a feather and some spirits. Iron filings have
    # no effects of their own, and a potion of enlarge person very much does.
    potion = _potion_for(chain.every_material, chain.methods)
    if potion is not None:
        name = chain.name or potion.name
        specs = potion.specs
        effects = [effectspec.render(s) for s in specs]
        drawbacks = []
        tier, rank = potion.tier, potion.rank
    else:
        name = chain.name or _name_for(mats, chain.methods)

    how = potion.how if potion is not None else _how_for(mats, specs)
    output = {
        "id": _slug(name), "name": name, "kind": "crafted", "craft": TRACK_ID,
        "tier": tier, "rank": rank, "count": 1,
        "effects": effects, "specs": specs,
        "from_materials": list(chain.every_material),
        "usable": bool(specs), "how": how,
        # Alchemy makes nothing you wear; the fields are here because the shared
        # inventory reads one shape for every craft's output, and a missing key is a
        # KeyError on somebody else's page.
        "wearable": False, "slot": None,
        "holds_spell": potion.spell if potion is not None else None,
        "caster_level": potion.caster_level if potion is not None else None,
        "glyph": KIND_GLYPH["potion"] if potion is not None else KIND_GLYPH["vessel"],
    }

    terms = check_terms(actor, level) if actor is not None else []
    bonus = sum(t["value"] for t in terms)
    return Result(
        name=name, tier=tier, rank=rank, stages=chain.stages, potency=potency,
        dc=dc, dc_terms=dc_terms, volatiles=volatiles,
        mishap=_mishap(volatiles), risky=risky, cleansed=cleansed,
        effects=effects, drawbacks=drawbacks, specs=specs, removed=removed,
        problems=problems, materials=[m.as_dict() for m in mats],
        output=output, consumes=dict(wanted),
        bonus=bonus, terms=terms,
        chance=_chance(dc, bonus, problems) if actor is not None else 0,
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


__all__ = ["ACQUISITION", "CLEANSING", "Chain", "CraftError", "FINISHING", "KIND_GLYPH",
           "Material", "POTENCY", "Result", "SHAPE_WORDS", "SpellPotion", "TRACK_ID",
           "VOLATILE_DC_STEP", "chain_from_body", "check_bonus", "check_terms",
           "from_dict", "get", "load_dir", "materials", "obtainable", "preview",
           "spell_potion", "spell_potion_from_dict", "spell_potions"]
