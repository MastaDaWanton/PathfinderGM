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
from typing import NamedTuple

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

    # Bestiary ecology lines say "any (Plane of Fire)" and "any (Hell)" rather than
    # naming an elemental plane in full.
    "plane of": "planar", "hell": "planar", "heaven": "planar", "abaddon": "planar",
    "aquatic": "coast", "underwater": "coast", "river": "coast", "lake": "coast",
    "elemental plane": "planar", "ethereal": "planar", "astral": "planar",
    "planar": "planar", "abyss": "planar", "celestial": "planar",
    "river oceanus": "planar",

    # Added after counting: 281 of the 782 core stat blocks carried environment prose
    # that produced no biome at all. Every word below was taken from that failure list
    # rather than guessed at — the whole vocabulary of the Environment lines is only a
    # hundred distinct words, so it could be read end to end.
    #
    # "plane" bare, because "any (Negative Energy Plane)" and "any (Shadow Plane)" never
    # say "plane of" and the alias above needed the preposition. The four proper nouns
    # are the only planes in the six Bestiaries that name themselves without the word.
    "plane": "planar", "nirvana": "planar", "dimension of": "planar",
    "outer space": "planar", "vacuum": "planar",
    # 26 lines say "water" with no other water word: "any water", "temperate water",
    # "warm fresh water", "any saltwater". Without these they came back with nothing.
    "water": "coast", "saltwater": "coast", "freshwater": "coast",
    "volcano": "mountain", "volcanic": "mountain",
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


# --- the second axis --------------------------------------------------------------------

# A Bestiary Environment line carries two things at once — "warm deserts" is a climate and
# a terrain — and the canonical list above cannot hold both, because it already mixes them:
# `desert` and `tundra` are half climate, `forest` and `mountain` are pure terrain. Folding
# climate into the biome would need a biome per pair (cold forest, warm forest, temperate
# forest...) and multiply the forage tables by three; dropping it would file a frost giant
# and a fire giant in the same mountains.
#
# So climate is kept as its own short list, and every consumer that cares reads both.
CLIMATES: dict[str, str] = {
    "cold": "Arctic and subarctic; snow lies for much of the year",
    "temperate": "The middle latitudes, with four seasons",
    "warm": "Tropical and subtropical; no winter worth the name",
}

# An empty climate list means the prose did not restrict it — "any forests" against
# "temperate forests". Absent is not the same as all three, and must not be written as all
# three, or a search for cold ground returns every forest creature in the book.
_CLIMATE_WORDS: dict[str, str] = {
    "cold": "cold", "arctic": "cold", "polar": "cold", "frigid": "cold",
    "subarctic": "cold", "glacier": "cold", "glacial": "cold",
    "temperate": "temperate",
    "warm": "warm", "hot": "warm", "tropical": "warm", "tropic": "warm",
    "subtropical": "warm", "equatorial": "warm",
}

# "any land" and "any" are different claims and 213 stat blocks make one or the other.
# Land excludes the sea and the caves; "any" excludes only the planes, because a devil's
# line reads "any (Hell)" rather than "any".
LAND = ("urban", "farmland", "grassland", "forest", "jungle", "swamp", "hills",
        "mountain", "desert", "tundra", "ruins")
EVERYWHERE = LAND + ("coast", "underground")

# Two entries in the canonical list are a climate and a terrain welded together, and they
# are the reason the two axes cannot simply be kept apart and left there. `tundra` is
# "Snowfield, ice and the far north" — cold plus open ground — and `jungle` is "Rainforest
# and tropical undergrowth" — warm plus forest. So when both halves of one of those pairs
# turn up in a line, the compound is written down as well.
#
# It is not a guess; it is the only way either word survives. The literal string "tundra"
# appears in one of the 782 Environment lines and "jungle" in three, and without this rule
# a search for either answered with almost nothing while "cold mountains" and "warm
# forests" sat there meaning exactly that.
#
# Forest and swamp do not become tundra: a taiga is still a forest and a frozen fen is
# still a fen. Nor does `desert` follow a climate either way — the book writes both "warm
# deserts" and "cold deserts", so dune and hardpan really are the terrain.
_TUNDRA_IF_COLD = ("grassland", "hills", "coast", "desert", "mountain")
_JUNGLE_IF_WARM = ("forest",)

# Words that are climate and nothing else, taken out before the terrain is read. Without
# this, "temperate or tropical swamps" came back as a swamp *and* a jungle, because
# `tropic` is an alias for jungle — the climate half of the line was being read twice, once
# correctly and once as ground.
_CLIMATE_ONLY = ("temperate", "subtropical", "tropical", "tropic", "equatorial",
                 "subarctic", "frigid", "glacial", "warm", "cold", "hot")

# Measured, not guessed: two core stat blocks read "warm de serts", a word the PDF
# extraction broke in half. It is the only split word in the entire Environment vocabulary.
_PDF_SPLITS = {"de serts": "deserts"}


class Environment(NamedTuple):
    """What one Environment line says, on both axes and about its own breadth."""

    biomes: list[str]
    climates: list[str]
    # True when the biome list is an expansion of "any"/"any land" rather than a habitat
    # the book chose. 254 of the 782 printed lines are one of those, and expanding them is
    # the only way a search for swamps finds the ghost that really can be there. The flag
    # is what afterwards tells that ghost from the 69 creatures the book put in a marsh.
    unrestricted: bool = False


def parse_environment(prose: str) -> Environment:
    """A Bestiary Environment line, split onto both axes.

    "warm deserts" -> (["desert"], ["warm"]); "any forests" -> (["forest"], []); "any land"
    -> (every land biome, [], unrestricted); "any (Hell)" -> (["planar"], []).

    An empty climate list is a real answer and means unrestricted. An empty biome list
    means the line said nothing this vocabulary can hold, which after the alias work above
    happens only for the one stat block whose Environment is blank.
    """
    low = (prose or "").strip().lower()
    for broken, whole in _PDF_SPLITS.items():
        low = low.replace(broken, whole)

    # "any non-cold underground" is one stat block, and it is the one that matters: `\b`
    # finds "cold" inside "non-cold" quite happily, so without this the ooze that cannot
    # survive the cold gets filed under cold.
    denied: set[str] = set()

    def _strip(m):
        denied.add(_CLIMATE_WORDS.get(m.group(1), ""))
        return " "

    low = re.sub(r"non-?\s*(\w+)", _strip, low)
    denied.discard("")

    climates = [c for c in CLIMATES
                if any(re.search(rf"\b{w}", low)
                       for w, mapped in _CLIMATE_WORDS.items() if mapped == c)]
    if denied and not climates:
        climates = [c for c in CLIMATES if c not in denied]

    terrain = low
    for word in _CLIMATE_ONLY:
        terrain = re.sub(rf"\b{word}\b", " ", terrain)
    found = detect(terrain, limit=len(BIOMES))
    # Before the expansion below, never after: `LAND` contains tundra, so reading the
    # implication afterwards would stamp "cold" on all 159 creatures whose line is "any".
    if "tundra" in found and not climates:
        climates = ["cold"]

    unrestricted = False
    if not found and low:
        if re.search(r"\bland\b|\baboveground\b|\bwilderness\b|\bnatural area\b", low):
            found, unrestricted = list(LAND), True
        elif re.search(r"\bany\b|\bair\b|\bsky\b", low):
            found, unrestricted = list(EVERYWHERE), True
        # "any wilderness" and "any land (wilderness)" are two stat blocks, and a
        # wilderness creature listed as a city encounter is a wrong answer, not a broad one.
        if "wilderness" in low:
            found = [b for b in found if b not in ("urban", "farmland")]

    for climate, pairs, compound in (("cold", _TUNDRA_IF_COLD, "tundra"),
                                     ("warm", _JUNGLE_IF_WARM, "jungle")):
        if (climate in climates and compound not in found
                and any(b in found for b in pairs)):
            found.append(compound)

    # Canonical order rather than match order, so the same line always writes the same
    # list and a rebuild of the content files produces no diff of its own.
    return Environment([b for b in BIOMES if b in found],
                       [c for c in CLIMATES if c in climates],
                       unrestricted)


def describe_climate(climate: str) -> str:
    return CLIMATES.get(climate, climate.title())


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
