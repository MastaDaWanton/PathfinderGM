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
        }


def from_dict(d: dict) -> Ingredient:
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
    )


def _flag(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("yes", "true", "1")
    return bool(value)


def load_dir(path: str | Path) -> dict[str, dict]:
    """Raw entries from a directory, as dicts so they can be merged before they are built.

    Two shapes are accepted, because two things write here: the shipped corpus is one file
    holding a list, and the editor writes one file per thing it edits. Reading only the
    first shape meant an edit saved successfully, appeared in the editor when reopened, and
    never reached play — the worst of both, because nothing reported a problem.
    """
    out: dict[str, dict] = {}
    for p in sorted(Path(path).glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries = data.get("ingredients") if isinstance(data, dict) else None
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


def get(ingredient_id: str) -> Ingredient:
    ing = all_ingredients().get((ingredient_id or "").strip().lower())
    if ing is None:
        raise KeyError(f"no ingredient {ingredient_id!r}")
    return ing


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
