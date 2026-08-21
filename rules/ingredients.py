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

import json
from dataclasses import dataclass, field
from pathlib import Path

from .worldclass import TIERS, tier_rank

# Named in the Herbalist and Blood Bending documents as growing somewhere specific, or
# invented for a setting. Whether Pangrella has them is a World Bible question; until the
# export carries flora, they are listed and marked rather than silently assumed present.
WORLD_FLORA = {
    "nura-stalk", "menhirite", "xian-tao", "selpeme-blossom", "tahtoalehti",
    "chasmyre-leaf", "hrondis-tears", "sherpa-s-friend", "orevine", "coldwood",
    "fey-cherry", "aelfengrape", "djinn-blossoms", "nahre-lotus", "salamander-orchids",
}


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

    @property
    def rank(self) -> int:
        return tier_rank(self.tier)

    @property
    def world_gated(self) -> bool:
        return self.id in WORLD_FLORA

    def as_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "kind": self.kind, "tier": self.tier,
            "rank": self.rank, "tier_inferred": self.tier_inferred, "aka": self.aka,
            "craft_dc": self.craft_dc, "source": self.source,
            "harvesting": self.harvesting, "text": self.text, "risky": self.risky,
            "world_gated": self.world_gated,
        }


def from_dict(d: dict) -> Ingredient:
    return Ingredient(
        id=d["id"], name=d["name"], kind=d.get("kind", "herb"),
        tier=d.get("tier", "common"), tier_inferred=bool(d.get("tier_inferred")),
        aka=d.get("aka", ""), craft_dc=d.get("craft_dc"), source=d.get("source", ""),
        harvesting=d.get("harvesting", ""), text=d.get("text", ""),
        risky=bool(d.get("risky")),
    )


def load_dir(path: str | Path) -> dict[str, Ingredient]:
    out: dict[str, Ingredient] = {}
    for p in sorted(Path(path).glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for raw in data.get("ingredients", []):
            ing = from_dict(raw)
            out[ing.id] = ing
    return out


_ALL: dict[str, Ingredient] | None = None


def all_ingredients() -> dict[str, Ingredient]:
    global _ALL
    if _ALL is None:
        from django.conf import settings

        _ALL = load_dir(Path(settings.BASE_DIR) / "content" / "ingredients")
        user = Path(settings.CAMPAIGN_DIR).parent / "homebrew" / "ingredients"
        if user.is_dir():
            _ALL.update(load_dir(user))
    return _ALL


def get(ingredient_id: str) -> Ingredient:
    ing = all_ingredients().get((ingredient_id or "").strip().lower())
    if ing is None:
        raise KeyError(f"no ingredient {ingredient_id!r}")
    return ing


def usable_at(rank: int) -> list[Ingredient]:
    """Everything a crafter of this tier may work with — theirs and everything below."""
    return [i for i in all_ingredients().values() if i.rank <= rank]
