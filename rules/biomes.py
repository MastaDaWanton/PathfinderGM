"""Where the characters are, in terms the rules can use.

Two different vocabularies have to meet here and neither was written for the other. The
World Bible export describes places in prose — Kaelinora's `Biomes` fact reads
"Pangrellan grasslands, Kyropticus deserts" — and the herb document describes habitats in
prose too: "grows in temperate forests", "damp, shadowy caves", "snowy tundras". Neither
will ever say `grassland`.

So there is one canonical list, and everything else is matched into it. The alternative —
letting each source keep its own words — means a herb that grows in "marshes" is never
found in a "swamp", and nothing anywhere reports the mismatch.
"""
from __future__ import annotations

import re

# The canonical set. Deliberately small: every extra biome is another axis the forage
# tables have to be populated across, and thirteen already covers everything both source
# documents describe.
BIOMES: dict[str, str] = {
    "urban": "Streets, yards and rooftops",
    "grassland": "Plains, steppe and open meadow",
    "farmland": "Tilled land, orchards and hedgerow",
    "forest": "Woodland, from open glade to deep timber",
    "jungle": "Rainforest and tropical undergrowth",
    "swamp": "Marsh, bog and fen",
    "hills": "Downs, moor and rough upland",
    "mountain": "Alpine slopes, crags and high plateau",
    "desert": "Dune, hardpan and badlands",
    "tundra": "Snowfield, ice and the far north",
    "coast": "Shore, tideline and salt marsh",
    "underground": "Cave, tunnel and the deep places",
    "ruins": "Barrows, battlefields and cursed ground",
    "planar": "Ground that is not of this world",
}

# Words that mean a biome. Longest first at match time, so "salt marsh" beats "marsh"
# and "mountain meadow" is not filed under meadow.
ALIASES: dict[str, str] = {
    "city": "urban", "town": "urban", "street": "urban", "alley": "urban",
    "rooftop": "urban", "sewer": "urban", "market": "urban",

    "grass": "grassland", "grassland": "grassland", "plain": "grassland",
    "prairie": "grassland", "steppe": "grassland", "savanna": "grassland",
    "meadow": "grassland", "veldt": "grassland", "open field": "grassland",
    "field": "grassland", "lowland": "grassland",

    "farm": "farmland", "orchard": "farmland", "hedgerow": "farmland",
    "pasture": "farmland", "vineyard": "farmland", "garden": "farmland",
    "cultivated": "farmland", "grown by": "farmland",

    "forest": "forest", "wood": "forest", "woodland": "forest", "timber": "forest",
    "glade": "forest", "grove": "forest", "thicket": "forest", "taiga": "forest",
    "copse": "forest", "tree": "forest",

    "jungle": "jungle", "rainforest": "jungle", "tropic": "jungle",

    "swamp": "swamp", "marsh": "swamp", "bog": "swamp", "fen": "swamp",
    "mire": "swamp", "wetland": "swamp", "moor": "hills",

    "hill": "hills", "down": "hills", "upland": "hills", "highland": "hills",

    "mountain": "mountain", "alpine": "mountain", "peak": "mountain",
    "crag": "mountain", "plateau": "mountain", "summit": "mountain",
    "mountaintop": "mountain", "cliff": "mountain",

    "desert": "desert", "dune": "desert", "arid": "desert", "badland": "desert",
    "oasis": "desert", "wasteland": "desert",

    "tundra": "tundra", "arctic": "tundra", "polar": "tundra", "glacier": "tundra",
    "snow": "tundra", "icy": "tundra", "frozen": "tundra", "northern climate": "tundra",
    "frost": "tundra",

    "coast": "coast", "shore": "coast", "beach": "coast", "tideline": "coast",
    "littoral": "coast", "reef": "coast", "estuary": "coast", "sea": "coast",
    "ocean": "coast", "riverbank": "coast", "bank": "coast",

    "cave": "underground", "cavern": "underground", "subterranean": "underground",
    "tunnel": "underground", "underdark": "underground", "underground": "underground",
    "mine": "underground", "crypt": "ruins",

    "ruin": "ruins", "battleground": "ruins", "battlefield": "ruins",
    "graveyard": "ruins", "barrow": "ruins", "tomb": "ruins", "cursed": "ruins",
    "haunted": "ruins", "interred": "ruins", "corpse": "ruins",

    "elemental plane": "planar", "ethereal": "planar", "astral": "planar",
    "planar": "planar", "abyss": "planar", "celestial": "planar",
    "river oceanus": "planar",
}

# Every phrase that means a biome, including the canonical names themselves — matching
# only the aliases meant `urban` was never detected, because the alias table lists
# "city" and "street" and never the word itself. Golden Maple Leaves, which "grow
# exclusively in urban areas", were filed as ordinary woodland.
_LOOKUP: dict[str, str] = {**{b: b for b in BIOMES}, **ALIASES}
# Longest first: "elemental plane" must win over "plane", "mountain" over "mount".
_ORDERED = sorted(_LOOKUP, key=len, reverse=True)


def canonical(word: str) -> str | None:
    w = (word or "").strip().lower()
    if w in BIOMES:
        return w
    return _LOOKUP.get(w)


def detect(text: str, limit: int = 4) -> list[str]:
    """Every biome a piece of prose points at, in the order they appear.

    Word-boundary matched rather than substring: without it "planar" is found inside
    "plane", "mine" inside "determine", and half the herb list ends up growing
    underground.
    """
    found: list[str] = []
    low = (text or "").lower()
    for phrase in _ORDERED:
        if not re.search(rf"\b{re.escape(phrase)}", low):
            continue
        biome = _LOOKUP[phrase]
        if biome not in found:
            found.append(biome)
        if len(found) >= limit:
            break
    return found


def from_world(world, entity) -> list[str]:
    """What biomes a place sits in, read from the export's own facts.

    Walks up through `parent_id` because the facts live where they belong: a town has
    `Urban Life` and `Governance`, and its continent has `Biomes`, `Terrain` and
    `Climate`. Reading only the location itself would have found nothing for every
    settlement in the world.
    """
    out: list[str] = ["urban"] if entity is not None and entity.kind == "CITY" else []
    seen = 0
    while entity is not None and seen < 6:
        facts = getattr(entity, "facts", None) or {}
        for key in ("Biomes", "Terrain", "Geography", "Climate", "Environment"):
            value = facts.get(key)
            if not value:
                continue
            for biome in detect(str(value)):
                if biome not in out:
                    out.append(biome)
        parent_id = getattr(entity, "parent_id", None)
        entity = world.get(parent_id) if parent_id else None
        seen += 1
    return out or ["grassland"]


def describe(biome: str) -> str:
    return BIOMES.get(biome, biome.title())
