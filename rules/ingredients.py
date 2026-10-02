"""What a crafter works with.

Ingredients are shipped content, layered the same way world classes are: a homebrew
directory in the user's data overlays the built-in set rather than replacing it, so a
corrected entry in a later build is not shadowed by a stale copy nobody remembers making.

Where an ingredient *comes from* is deliberately not settled here. Real herbs are
universal, monster parts belong to whatever you killed, and a handful — Nura Stalk,
Menhirite, Xian Tao — are world flora whose availability is a question for the world
rather than the rules. Everything loads; `world_gated` marks the ones whose presence in a
given world is not this module's call.
"""
from __future__ import annotations

import re

import json
from dataclasses import dataclass, field
from pathlib import Path

from .worldclass import TIERS, tier_rank
from pathfindergm import files

# Named in the Herbalist and Blood Bending documents as growing somewhere specific, or
# invented for a setting. Whether Pangrella has them is a World Bible question; until the
# export carries flora, they are listed and marked rather than silently assumed present.
WORLD_FLORA = {
    "nura-stalk", "menhirite", "xian-tao", "selpeme-blossom", "tahtoalehti",
    "chasmyre-leaf", "hrondis-tears", "sherpa-s-friend", "orevine", "coldwood",
    "fey-cherry", "aelfengrape", "djinn-blossoms", "nahre-lotus", "salamander-orchids",
}

# --- the herbalism revamp's vocabulary (docs/herbalism-contracts.md §2) ------------------
#
# Fixed lists, because the bench keys tables on them: Brew turns leaf and flower into an
# infusion and root, bark and berry into a decoction, and a part the table has never heard
# of would fall through to nothing. Anything outside these is a content error, and
# tests/test_ingredient_tags.py refuses it by name.
PARTS = ("leaf", "flower", "root", "bark", "berry", "seed", "sap", "resin", "fungus",
         "gland", "organ", "bone", "horn", "feather", "scale", "eye", "shell", "oil",
         "wax", "mineral", "liquid")
# How an effect reaches the body. The first five are the herbalist's; `external` is
# alchemy's alone (plan §5.2: the effect reaches outside the body or changes what others
# perceive — invisibility, light, flight, charming another, an area cloud, a blade coating
# that acts on a target). A herbal product drops an external effect; it never keeps one.
ROUTES = ("ingest", "skin", "eyes", "wound", "inhale", "external")
HERBAL_ROUTES = ROUTES[:-1]
SOLVENTS = ("oil", "alcohol", "vinegar", "water")
BASE_FORMS = ("salve", "balm", "cream")


def default_part(kind: str) -> str:
    """The part an entry is taken to be when nobody wrote one: the contract's defaults,
    so a homebrew herb saved before the field existed still lands on a real row of the
    bench's tables."""
    return {"monster part": "organ", "fungus": "fungus"}.get(str(kind or ""), "leaf")


def route_of(effect: dict) -> str:
    """The route one structured effect travels by.

    Absent means `ingest`: every effect authored before routes existed was a thing you
    drank or ate, and reading it that way keeps all of them behaving as they did.
    *Present but unrecognised* means `external`, the closed side. A homebrew typo such as
    "skn" read as the default would put an effect on the herbalist's bench that nobody
    decided belonged there; read as external, it is dropped and the shelf card says
    "alchemy only", which a person will notice and fix.
    """
    raw = str((effect or {}).get("route") or "").strip().lower()
    if not raw:
        return "ingest"
    return raw if raw in ROUTES else "external"


@dataclass
class Ingredient:
    id: str
    name: str
    kind: str = "herb"                 # herb | fungus | monster part | poison
    tier: str = "common"
    tier_inferred: bool = False
    aka: str = ""
    craft_dc: int | None = None
    source: str = ""                   # the creature, for monster parts
    harvesting: str = ""
    text: str = ""
    risky: bool = False
    # Where it grows, read from the entry's own description. `forageable` is False for
    # monster parts and finished poisons: those are cut off a corpse or brewed, not picked.
    biomes: list[str] = field(default_factory=list)
    biomes_inferred: bool = False
    forageable: bool = True
    # Authored effects (rules/effectspec.py), stored rather than re-derived. Deriving is
    # right while the parse is the only source of truth and wrong the moment a person may
    # correct one: the next parse would silently overwrite the edit.
    effects: list = field(default_factory=list)
    effects_converted: bool = False
    # How it has to be handled before it is any use. See `rules/herbprep.py` for what
    # each one means and why the defaults are these: everything authored before the
    # flags existed grinds, mixes, brews and keeps for a week, exactly as it did.
    #
    # They live on the dataclass rather than being read off a dict, because `from_dict`
    # builds this and quietly drops anything it has no field for — so the tags for 55
    # ingredients loaded, merged, and vanished on the way in, and every one of them
    # still read as an ordinary leaf.
    needs_extraction: bool = False
    volatile: bool = False
    can_grind: bool = True
    mix_raw: bool = True
    brew_raw: bool = True
    animal: bool = False
    liquid: bool = False
    # The herbalism revamp's fields (docs/herbalism-contracts.md §2). On the dataclass
    # for the reason the preparation flags above are: `from_dict` drops anything without
    # a field, and a tag that loads and then vanishes is worse than one never written.
    # Every default is the answer the bench gave before the field existed.
    #
    # `part`: what of the plant or creature is used. "" here means "not yet decided" and
    # `from_dict` always fills it from the kind (`default_part`), so a built Ingredient
    # never carries the empty string.
    part: str = ""
    # What this thickens, e.g. ["salve"]: beeswax, ground bark, ground sap or resin.
    base_for: list[str] = field(default_factory=list)
    # Strength as a neutralizer; Neutralize spends one dose of strength >= 1 per dose.
    neutralizer: int = 0
    # A carrier: "oil" for Infuse, "alcohol" for a tincture, "vinegar" for an acetum.
    solvent: str = ""
    # On both shelves: some effect is magical (planar flora, a monster part, anything
    # supernatural). The herbalist may use such an entry only for its body routes.
    hybrid: bool = False

    @property
    def rank(self) -> int:
        return tier_rank(self.tier)

    @property
    def pairs(self) -> list[tuple[str, dict]]:
        """Each effect as (card line, structured effect), from one walk.

        `lines` and `specs` used to be two separate walks over the same data, and nothing
        tied entry n of one to entry n of the other. That was harmless while a card
        printed every line the same way. It stopped being harmless the moment an effect's
        *type* began deciding which panel its line appears in: a crafting card that files
        "1d6 Constitution damage" under Effects because the two lists slipped by one is a
        bug nothing would report.

        Read from the stored effects when there are any, and parsed from the description
        only when there are not — so an authored correction wins over the extractor,
        which is the whole point of storing them. Both paths render through
        `effectspec.render`, so a parsed entry and a stored one cannot read differently;
        going through `Effect.text` here meant the card changed the moment somebody
        pressed save without altering anything.
        """
        from . import effectspec

        if self.effects:
            return [(effectspec.render(e), dict(e)) for e in self.effects]

        from . import effects as fx

        return [(effectspec.render(e.spec) if e.spec else e.text, dict(e.spec))
                for e in fx.extract(self.text)]

    @property
    def lines(self) -> list[str]:
        """What this ingredient does, as card lines."""
        return [line for line, _ in self.pairs]

    @property
    def specs(self) -> list[dict]:
        """The same effects as `lines`, structured rather than rendered.

        `lines` is what a card shows and this is what the engine can run. Same source and
        same precedence — authored effects win over the extractor — so a card and the
        thing that happens when you drink it can never disagree. Shorter than `lines`
        when a pattern found prose no authored type can hold.
        """
        return [spec for _, spec in self.pairs if spec]

    @property
    def world_gated(self) -> bool:
        return self.id in WORLD_FLORA

    @property
    def routes(self) -> list[str]:
        """The route of each structured effect, in `specs` order (`route_of`)."""
        return [route_of(s) for s in self.specs]

    @property
    def reagent(self) -> bool:
        """A bench reagent rather than a remedy: it carries, thickens or neutralizes."""
        return bool(self.solvent or self.base_for or self.neutralizer)

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "tier_inferred": self.tier_inferred, "aka": self.aka,
            "craft_dc": self.craft_dc, "source": self.source,
            "harvesting": self.harvesting, "text": self.text, "risky": self.risky,
            "world_gated": self.world_gated, "biomes": self.biomes,
            "biomes_inferred": self.biomes_inferred, "forageable": self.forageable,
            "effects": self.effects, "effects_converted": self.effects_converted,
            "lines": self.lines,
            "part": self.part, "base_for": list(self.base_for),
            "neutralizer": self.neutralizer, "solvent": self.solvent,
            "hybrid": self.hybrid, "routes": self.routes,
        }


def from_dict(d: dict) -> Ingredient:
    # Imported here rather than at the top: `herbprep` is the rules layer above this one
    # and importing it at module scope would tie the corpus to the bench.
    from . import herbprep

    return Ingredient(
        id=d["id"], name=d["name"], kind=d.get("kind", "herb"),
        tier=d.get("tier", "common"), tier_inferred=bool(d.get("tier_inferred")),
        aka=d.get("aka", ""), craft_dc=d.get("craft_dc"), source=d.get("source", ""),
        harvesting=d.get("harvesting", ""), text=d.get("text", ""),
        risky=bool(d.get("risky")),
        effects=list(d.get("effects") or []),
        effects_converted=bool(d.get("effects_converted")),
        biomes=list(d.get("biomes") or []),
        biomes_inferred=bool(d.get("biomes_inferred")),
        forageable=bool(d.get("forageable", True)),
        # The editor stores its choices as "yes"/"no" and the importer writes the same,
        # so a plain `bool()` would read the string "no" as True — which is how a flag
        # meaning "cannot be ground" would have come out meaning the opposite.
        needs_extraction=_flag(d.get("needs_extraction"), False),
        volatile=_flag(d.get("volatile"), False),
        can_grind=_flag(d.get("can_grind"), True),
        mix_raw=_flag(d.get("mix_raw"), True),
        brew_raw=_flag(d.get("brew_raw"), True),
        # Unstated for a monster part means yes: those are on the 48-hour clock because
        # of what they are, not because somebody ticked a box that did not exist when
        # the corpus was written.
        animal=_flag(d.get("animal"), d.get("kind", "") == "monster part"),
        # Same shape: unstated means the name decides. "Trollheart Sap" is a liquid
        # whether or not anyone ever tagged it, and only a liquid can be distilled.
        liquid=_flag(d.get("liquid"),
                     herbprep.looks_liquid(d.get("name", ""), d.get("kind", ""))),
        # The revamp's fields. Each one is read defensively, because the homebrew editor
        # writes strings ("yes", "2") and an old save writes nothing at all; either must
        # come out as the default the bench used before the field existed.
        part=(str(d.get("part") or "").strip().lower()
              or default_part(d.get("kind", "herb"))),
        base_for=_words(d.get("base_for")),
        neutralizer=_int(d.get("neutralizer")),
        solvent=str(d.get("solvent") or "").strip().lower(),
        hybrid=_flag(d.get("hybrid"), False),
    )


def _words(value) -> list[str]:
    """A list of lower-case words from a list, or from one comma-separated string."""
    if isinstance(value, str):
        value = value.split(",")
    return [str(v).strip().lower() for v in (value or []) if str(v).strip()]


def _int(value) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _flag(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("yes", "true", "1")
    return bool(value)


def load_dir(path: str | Path, key: str = "ingredients") -> dict[str, dict]:
    """Raw entries from a directory, as dicts so they can be merged before they are built.

    Two shapes are accepted, because two things write here: the shipped corpus is one file
    holding a list, and the editor writes one file per thing it edits. Reading only the
    first shape meant an edit saved successfully, appeared in the editor when reopened, and
    never reached play — the worst of both, because nothing reported a problem.

    `key` is the list's name inside a file holding many: "materials" when `reagents`
    reads the shared shelf. A file holding some other list (the spell-potion book) has
    no `id` at its top and is skipped.
    """
    out: dict[str, dict] = {}
    for p in sorted(Path(path).glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            files.unreadable(p, exc)
            continue
        entries = data.get(key) if isinstance(data, dict) else None
        if not isinstance(entries, list):
            entries = [data] if isinstance(data, dict) and data.get("id") else []
        for raw in entries:
            if raw.get("id"):
                out[raw["id"]] = raw
    return out


_ALL: dict[str, Ingredient] | None = None


def all_ingredients() -> dict[str, Ingredient]:
    """Shipped plus homebrew, through the shared overlay in `rules.registry`.

    This module used to carry its own copy of that walk, as six others did. They drifted:
    some merged and some replaced, some read a file holding one entry and some only a file
    holding a list. One place now, so a fix reaches every kind of content at once.
    """
    global _ALL
    if _ALL is None:
        from . import registry

        _ALL = {k: from_dict({**v, "id": k})
                for k, v in registry.load_raw("ingredients").items()}
    return _ALL


# --- the bench's reagents: carriers, bases and neutralizers -------------------------------
#
# **One row, both shelves.** Oil, alcohol, vinegar, beeswax and the neutralizers are not
# herbs, and three of them (Strong Spirits, White Vinegar, Beeswax) were already rows in
# `content/materials/alchemist-materials.json`, priced and bought at the market. A second
# copy under `content/ingredients/` would have been two prices for one jar of wax, and
# the copy nobody looks at drifts (CLAUDE.md: "grep for every copy of it"). So the
# herbalist reads the shared materials shelf instead, and a material is a herbalist
# reagent exactly when its row declares one of the herbalist's own fields: `solvent`,
# `base_for` or `neutralizer`. The alchemist's `Material` has no field for any of them
# and drops them on load, so the row serves both crafts unchanged.
#
# That is also why buying needs nothing new: the alchemist's counter already draws every
# priced, bought material on the shelf (`market.priced_from`, through
# `alchemist.obtainable("bought")`), so a reagent row with `obtain`, `market` and
# `price_gp` is for sale wherever alchemy's stock is.
#
# Kept out of `all_ingredients()` on purpose. That dict is the herb corpus: foraging
# walks it, the herbarium counts it, the homebrew page lists it as shipped herbs, and a
# scheme picks a random entry of it as a gift. A jar of vinegar in any of those would be
# wrong. `get` falls back to the reagents so a chain or a satchel id still resolves.
_REAGENTS: dict[str, Ingredient] | None = None


def reagents() -> dict[str, Ingredient]:
    """Every material on the shared shelf that the herbalist's bench can use, by id."""
    global _REAGENTS
    if _REAGENTS is None:
        from django.conf import settings

        raw = load_dir(Path(settings.BASE_DIR) / "content" / "materials", key="materials")
        # The homebrew overlay, as the alchemist reads it (`alchemist.materials`): user
        # data layered over the shipped rows, never replacing the folder.
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "materials"
        if user.is_dir():
            raw.update(load_dir(user, key="materials"))
        out: dict[str, Ingredient] = {}
        for k, row in raw.items():
            if not (row.get("solvent") or row.get("base_for") or row.get("neutralizer")):
                continue
            out[k] = from_dict({
                **row, "id": k,
                # One kind for the herbalist's shelf, whatever the alchemist files it
                # under ("solvent", "treatment", "salt"), so the bench's kind-keyed
                # tables need one new row and not four.
                "kind": "reagent",
                "forageable": False,
                # A carrier pours: Infuse and Steep need it to be a liquid, and the name
                # test in `herbprep.looks_liquid` does not know "Strong Spirits".
                "liquid": row.get("liquid", bool(row.get("solvent"))),
            })
        _REAGENTS = out
    return _REAGENTS


def shelf() -> dict[str, Ingredient]:
    """What the herbalist's bench can hold: the herb corpus and the reagents.

    A corpus id wins over a reagent with the same id, so a herb can never be shadowed
    by a material that happens to share its slug.
    """
    return {**reagents(), **all_ingredients()}


def get(ingredient_id: str) -> Ingredient:
    key = (ingredient_id or "").strip().lower()
    ing = all_ingredients().get(key) or reagents().get(key)
    if ing is None:
        raise KeyError(f"no ingredient {ingredient_id!r}")
    return ing


def reagent_named(text: str) -> Ingredient | None:
    """The reagent a bought jar is, from its name or id, exactly; or None.

    A purchase lands on the sheet as stock named for the material ("Beeswax", by
    `goods.deliver`), so the bench needs the name to come back to the reagent. Exact,
    not the prose search `by_name` does: "Strong Spirits" is one thing, and "spirits"
    in a sentence is not a jar of it.
    """
    said = " ".join(str(text or "").split()).strip().lower()
    if not said:
        return None
    for k, item in reagents().items():
        if said in (k, item.name.lower()):
            return item
    return None


def by_name(text: str) -> Ingredient | None:
    """The ingredient a piece of prose is naming, or None.

    The GM hands things over in words — "three sprigs of woundwort", "a salamander
    ember gland" — and the only way a satchel can take one is if the name resolves.
    Matched on the whole name appearing in the text rather than the other way round,
    longest first, so "Juniper Berry" is not answered with "Juniper".

    Deliberately not fuzzy. A near-miss here would put the wrong herb in the pot and
    the player would craft with it for a week.
    """
    said = " ".join(str(text or "").split()).strip().lower()
    if not said:
        return None
    everything = all_ingredients()
    if said in everything:
        return everything[said]
    for item in sorted(everything.values(), key=lambda i: len(i.name), reverse=True):
        name = item.name.lower()
        if said == name or re.search(rf"\b{re.escape(name)}\b", said):
            return item
    return None


def usable_at(rank: int) -> list[Ingredient]:
    """Everything a crafter of this tier may work with — theirs and everything below."""
    return [i for i in all_ingredients().values() if i.rank <= rank]
